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
    OrderIntent,
    OrderResult,
    PositionSnapshot,
)
from .engine import ExecutionDisabled, ExecutionEngine, describe_results
from .guard import OrderGuard
from .journal import ExecutionJournal, default_journal_path
from .reconciler import client_order_id, plan_orders
from .sizing import DEFAULT_TARGET_WEIGHTS, TargetWeightPolicy

__all__ = [
    "BUY",
    "SELL",
    "STATUS_DRY_RUN",
    "STATUS_DUPLICATE",
    "STATUS_ERROR",
    "STATUS_REJECTED",
    "STATUS_SUBMITTED",
    "AccountSnapshot",
    "Broker",
    "DEFAULT_TARGET_WEIGHTS",
    "ExecutionDisabled",
    "ExecutionEngine",
    "ExecutionJournal",
    "ExecutionPlan",
    "OrderGuard",
    "OrderIntent",
    "OrderResult",
    "PositionSnapshot",
    "TargetWeightPolicy",
    "client_order_id",
    "default_journal_path",
    "describe_results",
    "plan_orders",
]
