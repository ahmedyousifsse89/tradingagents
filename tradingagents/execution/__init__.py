"""Broker execution layer: turn 5-tier agent ratings into broker orders.

Import surface is deliberately small. ``AlpacaBroker`` is *not* re-exported
here because importing it pulls in the optional ``alpaca-py`` dependency;
import it from :mod:`tradingagents.execution.alpaca` when you need it, or let
:class:`ExecutionEngine` construct it lazily.
"""

from .broker import (
    BUY,
    SELL,
    STATUS_DRY_RUN,
    STATUS_DUPLICATE,
    STATUS_ERROR,
    STATUS_REJECTED,
    STATUS_SUBMITTED,
    AccountSnapshot,
    Broker,
    ExecutionPlan,
    FillInfo,
    OrderIntent,
    OrderResult,
    PositionSnapshot,
)
from .engine import ExecutionDisabled, ExecutionEngine, describe_results
from .fills import EntryFillLookup, entry_fill_lookup
from .guard import OrderGuard
from .journal import ExecutionJournal, default_journal_path
from .portfolio_context import fetch_portfolio_context, render_portfolio_context
from .reconciler import client_order_id, plan_orders
from .risk import (
    HALT_DAILY_DRAWDOWN,
    HALT_MANUAL,
    HALT_TOTAL_DRAWDOWN,
    KillSwitch,
    RiskState,
    default_risk_state_path,
    kill_switch_from_config,
)
from .sizing import DEFAULT_TARGET_WEIGHTS, TargetWeightPolicy

__all__ = [
    "BUY",
    "SELL",
    "STATUS_DRY_RUN",
    "STATUS_DUPLICATE",
    "STATUS_ERROR",
    "STATUS_REJECTED",
    "STATUS_SUBMITTED",
    "HALT_DAILY_DRAWDOWN",
    "HALT_MANUAL",
    "HALT_TOTAL_DRAWDOWN",
    "AccountSnapshot",
    "Broker",
    "DEFAULT_TARGET_WEIGHTS",
    "ExecutionDisabled",
    "ExecutionEngine",
    "ExecutionJournal",
    "EntryFillLookup",
    "ExecutionPlan",
    "FillInfo",
    "KillSwitch",
    "OrderGuard",
    "OrderIntent",
    "OrderResult",
    "PositionSnapshot",
    "RiskState",
    "TargetWeightPolicy",
    "client_order_id",
    "default_journal_path",
    "default_risk_state_path",
    "describe_results",
    "entry_fill_lookup",
    "fetch_portfolio_context",
    "kill_switch_from_config",
    "plan_orders",
    "render_portfolio_context",
]
