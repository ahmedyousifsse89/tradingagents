"""Unattended operation: watchlist, scheduled runs, and run history."""

from .history import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_HALTED,
    STATUS_RUNNING,
    RunHistory,
    RunRecord,
    default_history_path,
    new_run_id,
)
from .runner import RunnerBusy, TradingRunner
from .watchlist import Watchlist, default_watchlist_path

__all__ = [
    "STATUS_COMPLETED",
    "STATUS_FAILED",
    "STATUS_HALTED",
    "STATUS_RUNNING",
    "RunHistory",
    "RunRecord",
    "RunScheduler",
    "RunnerBusy",
    "TradingRunner",
    "Watchlist",
    "default_history_path",
    "default_watchlist_path",
    "new_run_id",
]


def __getattr__(name):
    # RunScheduler pulls in APScheduler, an optional extra. Keep it out of the
    # eager import path so `import tradingagents.runner` works without it.
    if name == "RunScheduler":
        from .scheduler import RunScheduler

        return RunScheduler
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
