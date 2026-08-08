"""Last checks between a planned order and a live broker call.

Every rejection here is a reason an order should *not* go out even though the
reconciler wanted it: the account is blocked, the market is shut, the order is
too large, too small, too numerous, or has already been placed. The guard is
pure — it decides, it does not submit — so the engine can apply the same
checks identically in dry-run and live mode.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .broker import AccountSnapshot, OrderIntent
from .journal import ExecutionJournal


class OrderGuard:
    """Reject unsafe or redundant order intents."""

    def __init__(
        self,
        journal: ExecutionJournal,
        *,
        min_order_notional: float = 10.0,
        max_orders_per_day: int = 20,
        max_position_weight: float = 0.10,
        allow_when_market_closed: bool = False,
    ):
        self.journal = journal
        self.min_order_notional = min_order_notional
        self.max_orders_per_day = max_orders_per_day
        self.max_position_weight = max_position_weight
        self.allow_when_market_closed = allow_when_market_closed

    def duplicate_reason(self, intent: OrderIntent) -> Optional[str]:
        """Non-None when this exact order already reached the broker."""
        if intent.client_order_id in self.journal.submitted_client_order_ids():
            return (
                f"client_order_id {intent.client_order_id} already submitted; "
                f"refusing to place {intent.symbol} twice"
            )
        return None

    def reject_reason(
        self,
        intent: OrderIntent,
        account: AccountSnapshot,
        market_open: bool,
        *,
        now: Optional[datetime] = None,
    ) -> Optional[str]:
        """Non-None when the order must not be placed. Checked in severity order."""
        if account.trading_blocked:
            return "broker reports trading_blocked on this account"

        if not market_open and not self.allow_when_market_closed:
            return "market is closed and allow_when_market_closed is off"

        notional = self._estimated_notional(intent)

        if notional is not None and notional < self.min_order_notional:
            return (
                f"order notional {notional:.2f} below minimum "
                f"{self.min_order_notional:.2f}"
            )

        cap = self.max_position_weight * account.equity
        if notional is not None and notional > cap:
            return (
                f"order notional {notional:.2f} exceeds per-order cap {cap:.2f} "
                f"({self.max_position_weight:.0%} of equity)"
            )

        today = (now or datetime.now(timezone.utc)).date().isoformat()
        placed_today = self.journal.submitted_count_on(today)
        if placed_today >= self.max_orders_per_day:
            return (
                f"daily order cap reached: {placed_today} submitted on {today}, "
                f"limit {self.max_orders_per_day}"
            )

        return None

    def _estimated_notional(self, intent: OrderIntent) -> Optional[float]:
        """Dollar size of the intent, or None when it cannot be estimated.

        Quantity orders carry no price, so the reconciler's own
        current-vs-target values are used instead; those come from broker
        position data and are accurate enough for a sanity bound.
        """
        if intent.notional is not None:
            return abs(intent.notional)
        delta = abs(intent.delta_value)
        return delta if delta > 0 else None
