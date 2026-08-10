"""Glue between agent ratings and the broker.

Four independent switches stand between a rating and a real-money order, and
all four must be set the permissive way for money to move:

1. ``execution_enabled`` — master switch, off by default.
2. ``execution_dry_run`` — on by default; when on, orders are planned,
   guarded, and journalled but never sent.
3. ``alpaca_live`` — selects the live endpoint over the paper one.
4. ``TRADINGAGENTS_ALPACA_ALLOW_LIVE`` — environment opt-in checked inside
   :class:`~.alpaca.AlpacaBroker`.

Guards run identically in dry-run and live mode, so a clean dry run is
evidence about the orders that would actually have gone out.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Sequence

from tradingagents.default_config import DEFAULT_CONFIG

from .broker import (
    SELL,
    STATUS_DRY_RUN,
    STATUS_DUPLICATE,
    STATUS_REJECTED,
    Broker,
    ExecutionPlan,
    OrderIntent,
    OrderResult,
)
from .guard import OrderGuard
from .journal import ExecutionJournal, default_journal_path
from .reconciler import client_order_id, plan_orders
from .risk import KillSwitch, kill_switch_from_config
from .sizing import TargetWeightPolicy

logger = logging.getLogger(__name__)


class ExecutionDisabled(RuntimeError):
    """Raised when a submission is attempted with ``execution_enabled`` off."""


class ExecutionEngine:
    """Plan, guard, journal, and (optionally) submit orders for ratings."""

    def __init__(
        self,
        config: Optional[dict] = None,
        broker: Optional[Broker] = None,
        journal: Optional[ExecutionJournal] = None,
        kill_switch: Optional[KillSwitch] = None,
    ):
        self.config = dict(config or DEFAULT_CONFIG)
        self.dry_run = bool(self.config.get("execution_dry_run", True))
        self.enabled = bool(self.config.get("execution_enabled", False))

        journal_path = default_journal_path(self.config)
        if journal is None and journal_path is None:
            raise ValueError(
                "no journal path could be resolved; set execution_journal_path "
                "or data_cache_dir in config"
            )
        self.journal = journal or ExecutionJournal(journal_path)

        self.policy = TargetWeightPolicy(
            weights=self.config.get("execution_target_weights"),
            max_position_weight=self.config.get("execution_max_position_weight", 0.10),
        )
        self.guard = OrderGuard(
            self.journal,
            min_order_notional=self.config.get("execution_min_order_notional", 10.0),
            max_orders_per_day=self.config.get("execution_max_orders_per_day", 20),
            max_position_weight=self.config.get("execution_max_position_weight", 0.10),
            allow_when_market_closed=self.config.get(
                "execution_allow_when_market_closed", False
            ),
        )

        self.kill_switch = kill_switch or kill_switch_from_config(self.config)
        self._broker = broker

    # ---- broker ------------------------------------------------------

    @property
    def broker(self) -> Broker:
        if self._broker is None:
            from .alpaca import AlpacaBroker

            self._broker = AlpacaBroker(live=bool(self.config.get("alpaca_live", False)))
        return self._broker

    # ---- planning ----------------------------------------------------

    def plan(self, ratings: Dict[str, str], *, trade_date: str) -> ExecutionPlan:
        """Compute the orders that would move the book to its target weights."""
        account = self.broker.get_account()
        positions = self.broker.get_positions()
        return plan_orders(
            ratings,
            account,
            positions,
            self.policy,
            trade_date=trade_date,
            min_order_notional=self.config.get("execution_min_order_notional", 10.0),
            max_gross_exposure=self.config.get("execution_max_gross_exposure", 0.80),
            fractional_shares=self.config.get("execution_fractional_shares", True),
            price_lookup=getattr(self.broker, "get_price", None),
        )

    # ---- execution ---------------------------------------------------

    def execute_ratings(
        self, ratings: Dict[str, str], *, trade_date: str
    ) -> List[OrderResult]:
        """Plan and then place (or dry-run) orders for ``ratings``.

        ``ratings`` maps ticker to a 5-tier rating string, i.e. the second
        element of :meth:`TradingAgentsGraph.propagate`'s return value.
        """
        if not self.dry_run and not self.enabled:
            raise ExecutionDisabled(
                "execution_dry_run is off but execution_enabled is not set; "
                "refusing to submit orders"
            )

        execution_plan = self.plan(ratings, trade_date=trade_date)
        for note in execution_plan.skipped:
            logger.info("execution plan skipped: %s", note)

        halt_detail = self._halt_detail(
            execution_plan.account.equity, trade_date=trade_date
        )
        market_open = self.broker.is_market_open()

        results: List[OrderResult] = []
        for intent in execution_plan.intents:
            if halt_detail:
                # Uniform with every other guard: a halt rejects in dry-run
                # mode too, so a dry run keeps mirroring what live would do.
                result = OrderResult(
                    intent=intent, status=STATUS_REJECTED, detail=halt_detail
                )
            else:
                result = self._execute_one(intent, execution_plan, market_open)
            self.journal.append(result.to_record())
            results.append(result)
        return results

    def _halt_detail(self, equity: float, *, trade_date: str = "") -> str:
        """Update the kill switch with current equity; return why it blocks, if it does.

        A switch that trips *here* rather than at run start means equity fell
        during the run itself — precisely the case where waiting for the next
        scheduled pass to liquidate is too slow. So the flatten happens now,
        on the transition, not once per subsequent blocked order.
        """
        if self.kill_switch is None:
            return ""

        was_halted = self.kill_switch.load().halted
        state = self.kill_switch.evaluate(equity)
        if not state.halted:
            return ""

        detail = f"kill switch active ({state.halt_reason}): {state.halt_detail}"
        if not was_halted and self.config.get("risk_flatten_on_halt", False):
            detail += "; " + self._flatten_on_trip(trade_date)
        return detail

    def _flatten_on_trip(self, trade_date: str) -> str:
        try:
            results = self.flatten_all(
                trade_date=trade_date or date.today().isoformat(),
                reason="kill-switch-flatten",
            )
        except Exception as exc:
            logger.exception("flatten-on-halt failed")
            return f"flatten failed ({type(exc).__name__}: {exc})"
        closed = [r.intent.symbol for r in results if r.submitted or self.dry_run]
        if not closed:
            return "flatten produced no orders"
        return f"flattened {len(closed)} position(s): {', '.join(closed)}"

    def risk_status(self) -> Optional[dict]:
        """Kill-switch snapshot, or None when the kill switch is disabled."""
        return self.kill_switch.status() if self.kill_switch else None

    def flatten_all(self, *, trade_date: str, reason: str = "flatten") -> List[OrderResult]:
        """Sell every open position at market.

        Irreversible and unconditional — it ignores ratings, targets, and the
        kill switch's halt state, because its whole purpose is to be usable
        once the kill switch has tripped. Callers are responsible for deciding
        that flattening is wanted; nothing here second-guesses that.
        """
        if not self.dry_run and not self.enabled:
            raise ExecutionDisabled(
                "execution_dry_run is off but execution_enabled is not set; "
                "refusing to submit orders"
            )

        positions = self.broker.get_positions()
        # Flatten ids are unique per invocation, not per ticker+date like a
        # rating-driven order. Deduplicating them would mean a second flatten
        # on the same day — after buying back in, or a retry after a partial
        # failure — is silently rejected by the broker as a duplicate.
        stamp = datetime.now(timezone.utc).strftime("%H%M%S%f")
        results: List[OrderResult] = []
        for pos in positions:
            if pos.qty <= 0:
                continue
            intent = OrderIntent(
                symbol=pos.symbol,
                side=SELL,
                client_order_id=client_order_id(
                    pos.symbol, trade_date, f"{reason}-{stamp}", SELL
                ),
                reason=f"{reason}: close {pos.qty:g} shares",
                qty=pos.qty,
                rating=reason,
                trade_date=trade_date,
                current_value=pos.market_value,
                target_value=0.0,
            )
            if self.dry_run:
                result = OrderResult(
                    intent=intent,
                    status=STATUS_DRY_RUN,
                    detail="dry run: position would be closed",
                )
            else:
                result = self.broker.submit(intent)
            self.journal.append(result.to_record())
            results.append(result)
        return results

    def execute_decision(
        self, ticker: str, rating: str, *, trade_date: str
    ) -> List[OrderResult]:
        """Single-ticker convenience wrapper around :meth:`execute_ratings`."""
        return self.execute_ratings({ticker: rating}, trade_date=trade_date)

    def _execute_one(
        self, intent: OrderIntent, execution_plan: ExecutionPlan, market_open: bool
    ) -> OrderResult:
        duplicate = self.guard.duplicate_reason(intent)
        if duplicate:
            return OrderResult(intent=intent, status=STATUS_DUPLICATE, detail=duplicate)

        existing = self.broker.find_order_by_client_id(intent.client_order_id)
        if existing:
            return OrderResult(
                intent=intent,
                status=STATUS_DUPLICATE,
                broker_order_id=existing,
                detail=f"broker already holds client_order_id {intent.client_order_id}",
            )

        rejection = self.guard.reject_reason(
            intent, execution_plan.account, market_open
        )
        if rejection:
            return OrderResult(intent=intent, status=STATUS_REJECTED, detail=rejection)

        if self.dry_run:
            return OrderResult(
                intent=intent,
                status=STATUS_DRY_RUN,
                detail="dry run: order passed all guards but was not submitted",
            )

        return self.broker.submit(intent)


def describe_results(results: Sequence[OrderResult]) -> str:
    """Human-readable summary for CLI output or logs."""
    if not results:
        return "No orders: the book already matches its target weights."
    lines = []
    for r in results:
        size = (
            f"${r.intent.notional:,.2f}"
            if r.intent.notional is not None
            else f"{r.intent.qty:g} sh"
        )
        lines.append(
            f"[{r.status:>9}] {r.intent.side.upper():<4} {r.intent.symbol:<8} "
            f"{size:>14}  {r.detail or r.intent.reason}"
        )
    return "\n".join(lines)
