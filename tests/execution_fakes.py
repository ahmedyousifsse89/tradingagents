"""Shared fake broker for the execution-layer tests.

Keeps every test offline and credential-free: nothing here talks to Alpaca.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from tradingagents.execution.broker import (
    STATUS_SUBMITTED,
    AccountSnapshot,
    OrderIntent,
    OrderResult,
    PositionSnapshot,
)


class FakeBroker:
    """In-memory :class:`~tradingagents.execution.broker.Broker`."""

    def __init__(
        self,
        equity: float = 100_000.0,
        positions: Optional[List[PositionSnapshot]] = None,
        market_open: bool = True,
        trading_blocked: bool = False,
        prices: Optional[Dict[str, float]] = None,
        fail_submit: bool = False,
    ):
        self._equity = equity
        self._positions = positions or []
        self._market_open = market_open
        self._trading_blocked = trading_blocked
        self._prices = prices or {}
        self.fail_submit = fail_submit
        self.submitted: List[OrderIntent] = []
        self._by_client_id: Dict[str, str] = {}

    def get_account(self) -> AccountSnapshot:
        return AccountSnapshot(
            equity=self._equity,
            cash=self._equity,
            buying_power=self._equity * 2,
            trading_blocked=self._trading_blocked,
        )

    def get_positions(self) -> List[PositionSnapshot]:
        return list(self._positions)

    def is_market_open(self) -> bool:
        return self._market_open

    def find_order_by_client_id(self, client_order_id: str) -> Optional[str]:
        return self._by_client_id.get(client_order_id)

    def get_price(self, symbol: str) -> Optional[float]:
        return self._prices.get(symbol)

    def submit(self, intent: OrderIntent) -> OrderResult:
        if self.fail_submit:
            raise RuntimeError("broker unavailable")
        self.submitted.append(intent)
        order_id = f"order-{len(self.submitted)}"
        self._by_client_id[intent.client_order_id] = order_id
        return OrderResult(
            intent=intent,
            status=STATUS_SUBMITTED,
            submitted=True,
            broker_order_id=order_id,
            detail="accepted",
        )


def position(symbol: str, qty: float, price: float) -> PositionSnapshot:
    """Convenience constructor: market value derived from qty * price."""
    return PositionSnapshot(
        symbol=symbol,
        qty=qty,
        market_value=qty * price,
        current_price=price,
        avg_entry_price=price,
    )
