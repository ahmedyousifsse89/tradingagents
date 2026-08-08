"""FastAPI control plane for the trading bot.

Serves the dashboard: account and position reads, watchlist editing, run
history, the order journal, manual run triggers, and the kill switch. Every
route except ``/health`` requires the bearer token.

Runs are executed on a single background worker thread. The HTTP layer never
blocks on an analysis pass — one full watchlist run is minutes of LLM calls,
far past any reasonable request timeout.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.execution.journal import ExecutionJournal, default_journal_path
from tradingagents.runner.runner import RunnerBusy, TradingRunner

from .auth import load_token, token_matches

logger = logging.getLogger(__name__)

CORS_ORIGINS_ENV = "TRADINGAGENTS_CORS_ORIGINS"


# ---- request models --------------------------------------------------


class RunRequest(BaseModel):
    tickers: Optional[List[str]] = Field(
        default=None,
        description="Tickers to analyse. Omit to use the stored watchlist.",
    )
    trade_date: Optional[str] = Field(
        default=None, description="ISO date stamped on the run. Defaults to today."
    )


class WatchlistRequest(BaseModel):
    tickers: List[str]


class HaltRequest(BaseModel):
    detail: str = "halted from the dashboard"


class FlattenRequest(BaseModel):
    confirm: str = Field(
        description="Must be the literal string FLATTEN to proceed.",
    )


# ---- app -------------------------------------------------------------


def create_app(
    config: Optional[dict] = None,
    runner: Optional[TradingRunner] = None,
    scheduler=None,
    api_token: Optional[str] = None,
) -> FastAPI:
    """Build the API. Raises at import/startup if no API token is configured."""
    config = dict(config or DEFAULT_CONFIG)
    expected_token = api_token or load_token()

    @asynccontextmanager
    async def lifespan(instance: FastAPI):
        yield
        instance.state.executor.shutdown(wait=False, cancel_futures=True)
        if instance.state.scheduler is not None:
            instance.state.scheduler.shutdown()

    app = FastAPI(
        title="TradingAgents Control API",
        description="Control plane for the TradingAgents execution bot.",
        version="0.1.0",
        lifespan=lifespan,
    )

    origins = [
        origin.strip()
        for origin in (os.environ.get(CORS_ORIGINS_ENV, "") or "").split(",")
        if origin.strip()
    ]
    if origins:
        # Only needed if a browser calls this API directly. The shipped
        # dashboard proxies server-side instead, so this stays empty by default.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )

    app.state.config = config
    app.state.runner = runner
    app.state.scheduler = scheduler
    app.state.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="run")

    def get_runner() -> TradingRunner:
        if app.state.runner is None:
            app.state.runner = TradingRunner(app.state.config)
        return app.state.runner

    def require_token(authorization: Optional[str] = Header(default=None)) -> None:
        if not token_matches(expected_token, authorization):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid or missing bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    auth = [Depends(require_token)]

    # ---- health (unauthenticated) ------------------------------------

    @app.get("/health", tags=["meta"])
    def health() -> Dict[str, Any]:
        """Liveness probe. Deliberately exposes no account or config detail."""
        return {"status": "ok"}

    # ---- status ------------------------------------------------------

    @app.get("/api/status", dependencies=auth, tags=["status"])
    def get_status() -> Dict[str, Any]:
        run = get_runner()
        payload: Dict[str, Any] = {
            "runner": run.status(),
            "risk": run.kill_switch.status() if run.kill_switch else None,
            "scheduler": {
                "running": bool(app.state.scheduler and app.state.scheduler.running),
                "next_run_time": (
                    app.state.scheduler.next_run_time() if app.state.scheduler else None
                ),
            },
            "account": None,
            "broker_error": None,
        }
        try:
            account = run.broker.get_account()
            payload["account"] = {
                "equity": account.equity,
                "cash": account.cash,
                "buying_power": account.buying_power,
                "trading_blocked": account.trading_blocked,
                "market_open": run.broker.is_market_open(),
            }
        except Exception as exc:
            # A broker outage must not blank the dashboard — the rest of the
            # status is still true and still worth showing.
            payload["broker_error"] = f"{type(exc).__name__}: {exc}"
        return payload

    @app.get("/api/positions", dependencies=auth, tags=["status"])
    def get_positions() -> Dict[str, Any]:
        run = get_runner()
        try:
            positions = run.broker.get_positions()
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"broker unavailable: {exc}")
        return {
            "positions": [
                {
                    "symbol": p.symbol,
                    "qty": p.qty,
                    "market_value": p.market_value,
                    "current_price": p.current_price,
                    "avg_entry_price": p.avg_entry_price,
                    "unrealized_pl": (p.current_price - p.avg_entry_price) * p.qty,
                }
                for p in positions
            ]
        }

    # ---- watchlist ---------------------------------------------------

    @app.get("/api/watchlist", dependencies=auth, tags=["watchlist"])
    def get_watchlist() -> Dict[str, Any]:
        return {"tickers": get_runner().watchlist.load()}

    @app.put("/api/watchlist", dependencies=auth, tags=["watchlist"])
    def put_watchlist(payload: WatchlistRequest) -> Dict[str, Any]:
        try:
            tickers = get_runner().watchlist.save(payload.tickers)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"tickers": tickers}

    @app.delete("/api/watchlist/{ticker}", dependencies=auth, tags=["watchlist"])
    def delete_watchlist_entry(ticker: str) -> Dict[str, Any]:
        return {"tickers": get_runner().watchlist.remove(ticker)}

    # ---- runs --------------------------------------------------------

    @app.get("/api/runs", dependencies=auth, tags=["runs"])
    def list_runs(limit: int = Query(default=25, ge=1, le=200)) -> Dict[str, Any]:
        return {"runs": get_runner().recent_runs(limit)}

    @app.get("/api/runs/{run_id}", dependencies=auth, tags=["runs"])
    def get_run(run_id: str) -> Dict[str, Any]:
        record = get_runner().get_run(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"no run with id {run_id}")
        return record

    @app.post("/api/runs", dependencies=auth, status_code=202, tags=["runs"])
    def trigger_run(payload: RunRequest) -> Dict[str, Any]:
        """Start a run in the background. 409 when one is already in flight."""
        run = get_runner()
        if run.is_running:
            raise HTTPException(
                status_code=409,
                detail=f"a run is already in progress ({run.running_run_id})",
            )

        def _execute():
            try:
                run.run_once(
                    payload.tickers, trigger="api", trade_date=payload.trade_date
                )
            except RunnerBusy as exc:
                logger.warning("api-triggered run skipped: %s", exc)
            except Exception:
                logger.exception("api-triggered run raised")

        app.state.executor.submit(_execute)
        return {"accepted": True, "tickers": payload.tickers or run.watchlist.load()}

    # ---- orders ------------------------------------------------------

    @app.get("/api/orders", dependencies=auth, tags=["orders"])
    def list_orders(limit: int = Query(default=100, ge=1, le=1000)) -> Dict[str, Any]:
        journal_path = default_journal_path(app.state.config)
        if journal_path is None:
            return {"orders": []}
        entries = ExecutionJournal(journal_path).entries()
        return {"orders": list(reversed(entries))[:limit]}

    # ---- risk --------------------------------------------------------

    @app.get("/api/risk", dependencies=auth, tags=["risk"])
    def get_risk() -> Dict[str, Any]:
        run = get_runner()
        if run.kill_switch is None:
            return {"enabled": False}
        return {"enabled": True, **run.kill_switch.status()}

    @app.post("/api/risk/halt", dependencies=auth, tags=["risk"])
    def halt(payload: HaltRequest) -> Dict[str, Any]:
        run = get_runner()
        if run.kill_switch is None:
            raise HTTPException(status_code=400, detail="kill switch is disabled")
        return run.kill_switch.halt(payload.detail).__dict__

    @app.post("/api/risk/resume", dependencies=auth, tags=["risk"])
    def resume() -> Dict[str, Any]:
        run = get_runner()
        if run.kill_switch is None:
            raise HTTPException(status_code=400, detail="kill switch is disabled")
        return run.kill_switch.resume("resumed from the dashboard").__dict__

    @app.post("/api/flatten", dependencies=auth, tags=["risk"])
    def flatten(payload: FlattenRequest) -> Dict[str, Any]:
        """Close every open position. Irreversible; requires an explicit confirm."""
        if payload.confirm != "FLATTEN":
            raise HTTPException(
                status_code=400,
                detail='confirm must be the literal string "FLATTEN"',
            )
        run = get_runner()
        try:
            results = run.engine.flatten_all(
                trade_date=date.today().isoformat(), reason="dashboard-flatten"
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"flatten failed: {exc}")
        return {"orders": [r.to_record() for r in results]}

    return app
