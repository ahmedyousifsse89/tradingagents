"""Broker-agnostic types and protocol for the execution layer.

The agent pipeline produces a 5-tier rating; everything downstream of that
is deterministic arithmetic plus a broker call. Keeping the broker behind a
protocol means the sizing policy, reconciler, and guard can all be tested
without network access or vendor credentials — the test suite substitutes a
fake implementation of :class:`Broker`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol, Sequence, runtime_checkable


# Order sides. Shorting is deliberately not modelled: the sizing policy
# floors target weights at zero, so a "Sell" on an unheld symbol is a no-op
# rather than an entry into a short position.
BUY = "buy"
SELL = "sell"


@dataclass(frozen=True)
class AccountSnapshot:
    """Point-in-time account state used to size orders."""

    equity: float
    cash: float
    buying_power: float
    trading_blocked: bool = False


@dataclass(frozen=True)
class PositionSnapshot:
    """A single open position."""

    symbol: str
    qty: float
    market_value: float
    current_price: float
    avg_entry_price: float = 0.0


@dataclass(frozen=True)
class OrderIntent:
    """A decided-upon order, before any broker call.

    Exactly one of ``notional`` and ``qty`` is set. Buys are placed as
    notional (dollar) orders so a target weight translates directly into an
    order without needing a quote; sells are placed as quantity orders so a
    full exit closes the position exactly rather than leaving dust behind.
    """

    symbol: str
    side: str
    client_order_id: str
    reason: str
    notional: Optional[float] = None
    qty: Optional[float] = None
    rating: str = ""
    trade_date: str = ""
    current_value: float = 0.0
    target_value: float = 0.0

    def __post_init__(self):
        if (self.notional is None) == (self.qty is None):
            raise ValueError(
                f"exactly one of notional/qty must be set for {self.symbol}: "
                f"notional={self.notional!r} qty={self.qty!r}"
            )
        if self.side not in (BUY, SELL):
            raise ValueError(f"side must be {BUY!r} or {SELL!r}, got {self.side!r}")

    @property
    def delta_value(self) -> float:
        """Signed dollar change this intent applies to the position."""
        return self.target_value - self.current_value


@dataclass(frozen=True)
class OrderResult:
    """Outcome of an intent: submitted, skipped by a guard, or dry-run."""

    intent: OrderIntent
    status: str
    submitted: bool = False
    broker_order_id: Optional[str] = None
    detail: str = ""

    def to_record(self) -> dict:
        """Flatten to a JSON-serialisable dict for the journal."""
        return {
            "symbol": self.intent.symbol,
            "side": self.intent.side,
            "notional": self.intent.notional,
            "qty": self.intent.qty,
            "client_order_id": self.intent.client_order_id,
            "rating": self.intent.rating,
            "trade_date": self.intent.trade_date,
            "current_value": self.intent.current_value,
            "target_value": self.intent.target_value,
            "reason": self.intent.reason,
            "status": self.status,
            "submitted": self.submitted,
            "broker_order_id": self.broker_order_id,
            "detail": self.detail,
        }


# Result statuses.
STATUS_SUBMITTED = "submitted"
STATUS_DRY_RUN = "dry_run"
STATUS_REJECTED = "rejected"      # a guard refused it
STATUS_DUPLICATE = "duplicate"    # already placed for this ticker+date+rating
STATUS_ERROR = "error"            # broker call raised


@runtime_checkable
class Broker(Protocol):
    """Minimum surface the execution engine needs from a broker."""

    def get_account(self) -> AccountSnapshot: ...

    def get_positions(self) -> Sequence[PositionSnapshot]: ...

    def is_market_open(self) -> bool: ...

    def submit(self, intent: OrderIntent) -> OrderResult: ...

    def find_order_by_client_id(self, client_order_id: str) -> Optional[str]:
        """Return the broker order id for a previously placed client id, else None."""
        ...

    def get_price(self, symbol: str) -> Optional[float]:
        """Latest trade price, or None when unavailable."""
        ...


@dataclass
class ExecutionPlan:
    """Full result of a planning pass, kept together for logging and review."""

    account: AccountSnapshot
    positions: Sequence[PositionSnapshot]
    intents: Sequence[OrderIntent] = field(default_factory=list)
    skipped: Sequence[str] = field(default_factory=list)
