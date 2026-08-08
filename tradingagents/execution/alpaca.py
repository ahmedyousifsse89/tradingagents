"""Alpaca implementation of the :class:`~.broker.Broker` protocol.

``alpaca-py`` is an optional dependency (``pip install -e ".[execution]"``) and
is imported lazily so the rest of the package — and the whole test suite —
works without it installed.

Live trading is gated twice. ``AlpacaBroker(live=True)`` is not enough on its
own: the environment variable ``TRADINGAGENTS_ALPACA_ALLOW_LIVE`` must also be
truthy. A stale config file or a mistyped flag therefore cannot by itself
point the engine at a real-money account.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from .broker import (
    BUY,
    STATUS_ERROR,
    STATUS_SUBMITTED,
    AccountSnapshot,
    OrderIntent,
    OrderResult,
    PositionSnapshot,
)

logger = logging.getLogger(__name__)

# Environment variables. The key names match Alpaca's own convention so an
# existing .env from another Alpaca tool works unchanged.
API_KEY_ENV = "ALPACA_API_KEY_ID"
SECRET_KEY_ENV = "ALPACA_API_SECRET_KEY"
ALLOW_LIVE_ENV = "TRADINGAGENTS_ALPACA_ALLOW_LIVE"

_TRUTHY = ("true", "1", "yes", "on")


class AlpacaCredentialsError(RuntimeError):
    """Raised when API keys are missing."""


class LiveTradingNotPermitted(RuntimeError):
    """Raised when live mode is requested without the environment opt-in."""


def live_opt_in_present(env: Optional[dict] = None) -> bool:
    """True when the environment grants permission for real-money orders."""
    source = env if env is not None else os.environ
    return str(source.get(ALLOW_LIVE_ENV, "")).strip().lower() in _TRUTHY


def _require_alpaca():
    try:
        from alpaca.trading.client import TradingClient  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depends on install extras
        raise ImportError(
            "alpaca-py is required for broker execution. "
            'Install it with: pip install -e ".[execution]"'
        ) from exc


class AlpacaBroker:
    """Thin, typed wrapper over ``alpaca-py``'s ``TradingClient``."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        *,
        live: bool = False,
        trading_client=None,
        data_client=None,
    ):
        if live and not live_opt_in_present():
            raise LiveTradingNotPermitted(
                "live trading requested but the environment opt-in is absent. "
                f"Set {ALLOW_LIVE_ENV}=true to allow real-money orders, or run "
                "against the paper endpoint by leaving alpaca_live unset."
            )
        self.live = live

        self._trading = trading_client
        self._data = data_client
        self._api_key = api_key or os.environ.get(API_KEY_ENV)
        self._secret_key = secret_key or os.environ.get(SECRET_KEY_ENV)

        if self._trading is None:
            _require_alpaca()
            if not self._api_key or not self._secret_key:
                raise AlpacaCredentialsError(
                    f"missing Alpaca credentials: set {API_KEY_ENV} and {SECRET_KEY_ENV}"
                )
            from alpaca.trading.client import TradingClient

            # paper is the inverse of live; alpaca-py picks the endpoint from it.
            self._trading = TradingClient(
                self._api_key, self._secret_key, paper=not live
            )

        logger.info(
            "AlpacaBroker ready against the %s endpoint",
            "LIVE" if live else "paper",
        )

    # ---- reads -------------------------------------------------------

    def get_account(self) -> AccountSnapshot:
        account = self._trading.get_account()
        return AccountSnapshot(
            equity=float(account.equity or 0),
            cash=float(account.cash or 0),
            buying_power=float(account.buying_power or 0),
            trading_blocked=bool(account.trading_blocked or account.account_blocked),
        )

    def get_positions(self) -> List[PositionSnapshot]:
        return [
            PositionSnapshot(
                symbol=p.symbol,
                qty=float(p.qty or 0),
                market_value=float(p.market_value or 0),
                current_price=float(p.current_price or 0),
                avg_entry_price=float(p.avg_entry_price or 0),
            )
            for p in self._trading.get_all_positions()
        ]

    def is_market_open(self) -> bool:
        return bool(self._trading.get_clock().is_open)

    def find_order_by_client_id(self, client_order_id: str) -> Optional[str]:
        """Broker-side duplicate check; None when the id is unknown."""
        try:
            order = self._trading.get_order_by_client_id(client_order_id)
        except Exception:
            # alpaca-py raises APIError (404) for an unknown client id. Any
            # other failure here must not be read as "safe to place again",
            # but the engine's journal check has already run, so treating a
            # lookup failure as "unknown" is acceptable and is logged.
            logger.debug("client order id lookup failed for %s", client_order_id)
            return None
        return str(order.id) if order is not None else None

    def get_price(self, symbol: str) -> Optional[float]:
        client = self._ensure_data_client()
        if client is None:
            return None
        try:
            from alpaca.data.requests import StockLatestTradeRequest

            trades = client.get_stock_latest_trade(
                StockLatestTradeRequest(symbol_or_symbols=symbol)
            )
            trade = trades.get(symbol)
            return float(trade.price) if trade is not None else None
        except Exception:
            logger.warning("latest-trade lookup failed for %s", symbol)
            return None

    def _ensure_data_client(self):
        if self._data is not None:
            return self._data
        if not self._api_key or not self._secret_key:
            return None
        try:
            from alpaca.data.historical import StockHistoricalDataClient

            self._data = StockHistoricalDataClient(self._api_key, self._secret_key)
        except ImportError:  # pragma: no cover - depends on install extras
            return None
        return self._data

    # ---- writes ------------------------------------------------------

    def submit(self, intent: OrderIntent) -> OrderResult:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        request = MarketOrderRequest(
            symbol=intent.symbol,
            notional=intent.notional,
            qty=intent.qty,
            side=OrderSide.BUY if intent.side == BUY else OrderSide.SELL,
            # Notional and fractional orders are DAY-only at Alpaca; using DAY
            # for everything also means an unfilled order expires at the close
            # rather than resting into the next session unattended.
            time_in_force=TimeInForce.DAY,
            client_order_id=intent.client_order_id,
        )

        try:
            order = self._trading.submit_order(request)
        except Exception as exc:
            logger.error("order submission failed for %s: %s", intent.symbol, exc)
            return OrderResult(
                intent=intent,
                status=STATUS_ERROR,
                submitted=False,
                detail=f"{type(exc).__name__}: {exc}",
            )

        return OrderResult(
            intent=intent,
            status=STATUS_SUBMITTED,
            submitted=True,
            broker_order_id=str(getattr(order, "id", "")) or None,
            detail=str(getattr(order, "status", "")),
        )
