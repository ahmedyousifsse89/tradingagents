"""Tests for the Alpaca broker adapter, especially the live-trading gate.

No network and no credentials: the ``TradingClient`` is always injected.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tradingagents.execution.alpaca import (
    ALLOW_LIVE_ENV,
    AlpacaBroker,
    LiveTradingNotPermitted,
    live_opt_in_present,
)
from tradingagents.execution.broker import BUY, SELL, OrderIntent


class StubTradingClient:
    def __init__(self, **overrides):
        self.account = overrides.get(
            "account",
            SimpleNamespace(
                equity="100000.5",
                cash="50000",
                buying_power="100000",
                trading_blocked=False,
                account_blocked=False,
            ),
        )
        self.positions = overrides.get("positions", [])
        self.clock = overrides.get("clock", SimpleNamespace(is_open=True))
        self.orders_by_client_id = overrides.get("orders_by_client_id", {})
        self.submitted = []
        self.submit_error = overrides.get("submit_error")

    def get_account(self):
        return self.account

    def get_all_positions(self):
        return self.positions

    def get_clock(self):
        return self.clock

    def get_order_by_client_id(self, client_order_id):
        if client_order_id not in self.orders_by_client_id:
            raise RuntimeError("404 order not found")
        return self.orders_by_client_id[client_order_id]

    def submit_order(self, order_data):
        if self.submit_error:
            raise self.submit_error
        self.submitted.append(order_data)
        return SimpleNamespace(id="broker-1", status="accepted")


def intent(side=BUY, **kwargs):
    payload = dict(
        symbol="NVDA",
        side=side,
        client_order_id="ta-abc",
        reason="test",
        rating="Buy",
        trade_date="2026-08-07",
    )
    payload.update(kwargs)
    payload.setdefault("notional" if side == BUY else "qty", 1_000.0)
    return OrderIntent(**payload)


# ---- the live gate ---------------------------------------------------


def test_live_requires_the_environment_opt_in(monkeypatch):
    monkeypatch.delenv(ALLOW_LIVE_ENV, raising=False)
    with pytest.raises(LiveTradingNotPermitted, match="environment opt-in is absent"):
        AlpacaBroker(live=True, trading_client=StubTradingClient())


@pytest.mark.parametrize("value", ["false", "0", "no", "", "  ", "maybe"])
def test_non_truthy_opt_in_still_blocks_live(monkeypatch, value):
    monkeypatch.setenv(ALLOW_LIVE_ENV, value)
    with pytest.raises(LiveTradingNotPermitted):
        AlpacaBroker(live=True, trading_client=StubTradingClient())


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on"])
def test_truthy_opt_in_allows_live(monkeypatch, value):
    monkeypatch.setenv(ALLOW_LIVE_ENV, value)
    broker = AlpacaBroker(live=True, trading_client=StubTradingClient())
    assert broker.live is True


def test_paper_mode_needs_no_opt_in(monkeypatch):
    monkeypatch.delenv(ALLOW_LIVE_ENV, raising=False)
    broker = AlpacaBroker(trading_client=StubTradingClient())
    assert broker.live is False


def test_live_opt_in_present_reads_the_environment():
    assert live_opt_in_present({ALLOW_LIVE_ENV: "true"}) is True
    assert live_opt_in_present({}) is False


# ---- reads -----------------------------------------------------------


def test_account_snapshot_coerces_strings():
    broker = AlpacaBroker(trading_client=StubTradingClient())
    account = broker.get_account()
    assert account.equity == pytest.approx(100000.5)
    assert account.trading_blocked is False


def test_account_blocked_flag_counts_as_trading_blocked():
    client = StubTradingClient(
        account=SimpleNamespace(
            equity="1",
            cash="1",
            buying_power="1",
            trading_blocked=False,
            account_blocked=True,
        )
    )
    assert AlpacaBroker(trading_client=client).get_account().trading_blocked is True


def test_positions_are_mapped():
    client = StubTradingClient(
        positions=[
            SimpleNamespace(
                symbol="NVDA",
                qty="12.5",
                market_value="1250",
                current_price="100",
                avg_entry_price="90",
            )
        ]
    )
    (pos,) = AlpacaBroker(trading_client=client).get_positions()
    assert pos.symbol == "NVDA"
    assert pos.qty == pytest.approx(12.5)
    assert pos.market_value == pytest.approx(1250.0)


def test_unknown_client_order_id_returns_none():
    broker = AlpacaBroker(trading_client=StubTradingClient())
    assert broker.find_order_by_client_id("ta-missing") is None


def test_known_client_order_id_returns_the_broker_id():
    client = StubTradingClient(
        orders_by_client_id={"ta-abc": SimpleNamespace(id="broker-9")}
    )
    assert AlpacaBroker(trading_client=client).find_order_by_client_id("ta-abc") == "broker-9"


# ---- writes ----------------------------------------------------------


def test_buy_submits_a_notional_day_order():
    from alpaca.trading.enums import OrderSide, TimeInForce

    client = StubTradingClient()
    result = AlpacaBroker(trading_client=client).submit(intent())
    (request,) = client.submitted
    assert request.symbol == "NVDA"
    assert request.notional == 1_000.0
    assert request.qty is None
    assert request.side == OrderSide.BUY
    assert request.time_in_force == TimeInForce.DAY
    assert request.client_order_id == "ta-abc"
    assert result.submitted is True
    assert result.broker_order_id == "broker-1"


def test_sell_submits_a_quantity_order():
    from alpaca.trading.enums import OrderSide

    client = StubTradingClient()
    AlpacaBroker(trading_client=client).submit(intent(side=SELL, qty=5.0))
    (request,) = client.submitted
    assert request.qty == 5.0
    assert request.notional is None
    assert request.side == OrderSide.SELL


def test_submission_error_becomes_an_error_result():
    client = StubTradingClient(submit_error=RuntimeError("insufficient buying power"))
    result = AlpacaBroker(trading_client=client).submit(intent())
    assert result.submitted is False
    assert result.status == "error"
    assert "insufficient buying power" in result.detail
