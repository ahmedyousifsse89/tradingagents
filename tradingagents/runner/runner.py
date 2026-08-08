"""Unattended pass over a watchlist: analyse, then execute as one batch.

Ordering matters here. The kill switch is checked *before* any analysis, so a
halted account costs nothing in LLM spend. Every ticker is then analysed, and
only afterwards are the ratings handed to the execution engine in a single
call — batching is what lets the gross-exposure cap see the whole book instead
of approving each name in ignorance of the others.

One run at a time. A scheduled fire that lands while a run is still going is
dropped rather than queued: two concurrent passes would both read the same
pre-trade positions and each size orders as if the other had not happened.
"""

from __future__ import annotations

import logging
import threading
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.execution.engine import ExecutionEngine
from tradingagents.execution.risk import kill_switch_from_config

from .history import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_HALTED,
    RunHistory,
    RunRecord,
    default_history_path,
    new_run_id,
    utcnow,
)
from .watchlist import Watchlist, default_watchlist_path

logger = logging.getLogger(__name__)


class RunnerBusy(RuntimeError):
    """Raised when a run is requested while another is in flight."""


class TradingRunner:
    """Owns the analyse-then-execute cycle and its persisted history."""

    def __init__(
        self,
        config: Optional[dict] = None,
        *,
        broker=None,
        engine: Optional[ExecutionEngine] = None,
        graph=None,
        watchlist: Optional[Watchlist] = None,
        history: Optional[RunHistory] = None,
    ):
        self.config = dict(config or DEFAULT_CONFIG)
        self._broker = broker
        self._engine = engine
        self._graph = graph

        watchlist_path = default_watchlist_path(self.config)
        history_path = default_history_path(self.config)
        if watchlist is None and watchlist_path is None:
            raise ValueError("no watchlist path could be resolved; set data_cache_dir")
        if history is None and history_path is None:
            raise ValueError("no run history path could be resolved; set data_cache_dir")

        self.watchlist = watchlist or Watchlist(watchlist_path)
        self.history = history or RunHistory(history_path)
        self.kill_switch = kill_switch_from_config(self.config)

        self._lock = threading.Lock()
        self._running_run_id: Optional[str] = None

    # ---- lazily built collaborators ----------------------------------

    @property
    def broker(self):
        if self._broker is None:
            from tradingagents.execution.alpaca import AlpacaBroker

            self._broker = AlpacaBroker(live=bool(self.config.get("alpaca_live", False)))
        return self._broker

    @property
    def engine(self) -> ExecutionEngine:
        if self._engine is None:
            self._engine = ExecutionEngine(
                self.config, broker=self.broker, kill_switch=self.kill_switch
            )
        return self._engine

    @property
    def graph(self):
        """The agent graph, built once and reused across runs.

        Construction creates LLM clients and compiles the LangGraph workflow,
        which is slow enough that rebuilding per run would dominate a
        single-ticker pass.
        """
        if self._graph is None:
            from tradingagents.graph.trading_graph import TradingAgentsGraph

            self._graph = TradingAgentsGraph(config=self.config, broker=self.broker)
        return self._graph

    # ---- state -------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running_run_id is not None

    @property
    def running_run_id(self) -> Optional[str]:
        return self._running_run_id

    def status(self) -> Dict[str, Any]:
        """Snapshot for the API: what the runner is doing and under what limits."""
        return {
            "running": self.is_running,
            "running_run_id": self._running_run_id,
            "watchlist": self.watchlist.load(),
            "schedule_enabled": bool(self.config.get("schedule_enabled", False)),
            "schedule_cron": self.config.get("schedule_cron"),
            "schedule_timezone": self.config.get("schedule_timezone", "UTC"),
            "execution_enabled": bool(self.config.get("execution_enabled", False)),
            "execution_dry_run": bool(self.config.get("execution_dry_run", True)),
            "alpaca_live": bool(self.config.get("alpaca_live", False)),
            "max_tickers": self.config.get("run_max_tickers", 10),
        }

    # ---- the cycle ---------------------------------------------------

    def run_once(
        self,
        tickers: Optional[Sequence[str]] = None,
        *,
        trigger: str = "manual",
        trade_date: Optional[str] = None,
    ) -> RunRecord:
        """Analyse ``tickers`` (default: the watchlist) and execute the result."""
        if not self._lock.acquire(blocking=False):
            raise RunnerBusy(f"a run is already in progress ({self._running_run_id})")

        record = RunRecord(
            run_id=new_run_id(),
            trigger=trigger,
            trade_date=trade_date or date.today().isoformat(),
            started_at=utcnow(),
        )
        self._running_run_id = record.run_id

        try:
            self._run_body(record, tickers)
        except Exception as exc:
            logger.exception("run %s failed", record.run_id)
            record.status = STATUS_FAILED
            record.note = f"{type(exc).__name__}: {exc}"
        finally:
            record.finished_at = utcnow()
            try:
                self.history.save(record)
            except Exception:
                # Losing the history write must not take down the caller's
                # thread — for a scheduled fire that would kill the job and
                # stop every future run. The record still goes back to the
                # caller; only the durable copy is lost.
                logger.exception("could not persist run %s", record.run_id)
            self._running_run_id = None
            self._lock.release()

        return record

    def _run_body(self, record: RunRecord, tickers: Optional[Sequence[str]]) -> None:
        explicit = bool(tickers)
        selected = list(tickers) if explicit else self.watchlist.load()
        max_tickers = self.config.get("run_max_tickers", 10)

        if max_tickers and len(selected) > max_tickers:
            if explicit:
                # The caller named these, so honour their order and just cap.
                record.note = (
                    f"{len(selected)} tickers requested; capped at {max_tickers} "
                    f"by run_max_tickers"
                )
                selected = selected[:max_tickers]
            else:
                selected = self._rotate(selected, max_tickers)
                record.note = (
                    f"watchlist has {len(self.watchlist.load())} tickers; this pass "
                    f"covers the {max_tickers} least recently analysed: "
                    f"{', '.join(selected)}"
                )
        record.tickers = selected

        if not selected:
            record.status = STATUS_COMPLETED
            record.note = record.note or "watchlist is empty; nothing to analyse"
            self.history.save(record)
            return

        # Kill switch before any LLM call: a halted account should cost nothing.
        halt = self._check_halt()
        if halt is not None:
            record.status = STATUS_HALTED
            record.note = halt
            self.history.save(record)
            logger.error("run %s aborted: %s", record.run_id, halt)
            return

        self.history.save(record)  # surface the in-flight run to the dashboard

        for ticker in selected:
            try:
                final_state, rating = self.graph.propagate(ticker, record.trade_date)
                record.ratings[ticker] = rating
                record.decisions[ticker] = final_state.get("final_trade_decision", "")
            except Exception as exc:
                # One bad ticker must not cost the whole pass — the others have
                # already been paid for.
                logger.exception("analysis failed for %s", ticker)
                record.errors[ticker] = f"{type(exc).__name__}: {exc}"
            self.history.save(record)

        if record.ratings:
            results = self.engine.execute_ratings(
                record.ratings, trade_date=record.trade_date
            )
            record.orders = [r.to_record() for r in results]

        record.status = STATUS_COMPLETED

    def _rotate(self, tickers: Sequence[str], limit: int) -> List[str]:
        """Pick the ``limit`` least recently analysed tickers.

        Taking the first N every pass means a watchlist longer than the cap has
        a permanent tail that is never looked at. Ordering by when each ticker
        was last analysed turns the cap into a rotation, so every name gets
        covered eventually. Ties and never-analysed tickers keep watchlist
        order, which makes a fresh watchlist behave exactly like the old
        first-N slice on its first pass.
        """
        last_seen: Dict[str, str] = {}
        for record in self.history.all():
            started = record.get("started_at", "")
            for ticker in record.get("tickers", []):
                key = str(ticker).upper()
                if started > last_seen.get(key, ""):
                    last_seen[key] = started

        order = {ticker: index for index, ticker in enumerate(tickers)}
        return sorted(
            tickers, key=lambda t: (last_seen.get(t.upper(), ""), order[t])
        )[:limit]

    def _check_halt(self) -> Optional[str]:
        """Return the halt message when trading is blocked, else None."""
        if self.kill_switch is None:
            return None
        try:
            equity = self.broker.get_account().equity
        except Exception as exc:
            # No equity reading means no way to know whether a drawdown limit
            # has been breached. Fail closed.
            return f"could not read account equity ({type(exc).__name__}: {exc})"

        state = self.kill_switch.evaluate(equity)
        if not state.halted:
            return None

        message = f"kill switch active ({state.halt_reason}): {state.halt_detail}"
        if self.config.get("risk_flatten_on_halt", False):
            message += "; " + self._flatten()
        return message

    def _flatten(self) -> str:
        try:
            results = self.engine.flatten_all(
                trade_date=date.today().isoformat(), reason="kill-switch-flatten"
            )
        except Exception as exc:
            logger.exception("flatten-on-halt failed")
            return f"flatten failed ({type(exc).__name__}: {exc})"
        closed = [r.intent.symbol for r in results if r.submitted]
        if not closed:
            return "flatten produced no submitted orders"
        return f"flattened {len(closed)} position(s): {', '.join(closed)}"

    # ---- convenience -------------------------------------------------

    def recent_runs(self, limit: int = 25) -> List[dict]:
        return self.history.recent(limit)

    def get_run(self, run_id: str) -> Optional[dict]:
        return self.history.get(run_id)
