"""Tests for turning target weights into concrete order intents."""

from __future__ import annotations

import pytest

from tests.execution_fakes import position
from tradingagents.execution.broker import BUY, SELL, AccountSnapshot
from tradingagents.execution.reconciler import client_order_id, plan_orders
from tradingagents.execution.sizing import TargetWeightPolicy

TRADE_DATE = "2026-08-07"


def account(equity=100_000.0):
    return AccountSnapshot(equity=equity, cash=equity, buying_power=equity * 2)


def plan(ratings, positions=(), equity=100_000.0, **kwargs):
    return plan_orders(
        ratings,
        account(equity),
        list(positions),
        kwargs.pop("policy", TargetWeightPolicy()),
        trade_date=TRADE_DATE,
        **kwargs,
    )


def test_buy_from_flat_uses_notional():
    result = plan({"NVDA": "Buy"})
    (intent,) = result.intents
    assert intent.side == BUY
    assert intent.notional == pytest.approx(8_000.0)
    assert intent.qty is None
    assert intent.target_value == pytest.approx(8_000.0)


def test_existing_position_only_trades_the_delta():
    # Already holding $6k of an 8% ($8k) target: buy the $2k gap, not $8k.
    result = plan({"NVDA": "Buy"}, positions=[position("NVDA", 60, 100.0)])
    (intent,) = result.intents
    assert intent.notional == pytest.approx(2_000.0)


def test_rerun_after_fill_produces_no_orders():
    # This is the property that makes the layer safe to re-run: once the
    # position matches the target, the same rating yields nothing.
    result = plan({"NVDA": "Buy"}, positions=[position("NVDA", 80, 100.0)])
    assert result.intents == []


def test_hold_leaves_the_position_untouched():
    result = plan({"NVDA": "Hold"}, positions=[position("NVDA", 33, 100.0)])
    assert result.intents == []


def test_sell_flattens_the_exact_share_count():
    result = plan({"NVDA": "Sell"}, positions=[position("NVDA", 42.5, 100.0)])
    (intent,) = result.intents
    assert intent.side == SELL
    assert intent.qty == pytest.approx(42.5)
    assert intent.notional is None
    assert intent.target_value == 0.0


def test_partial_reduction_sells_only_the_delta():
    # $10k held, Underweight targets 2% = $2k, so $8k / $100 = 80 shares go.
    result = plan({"NVDA": "Underweight"}, positions=[position("NVDA", 100, 100.0)])
    (intent,) = result.intents
    assert intent.side == SELL
    assert intent.qty == pytest.approx(80.0)


def test_sell_without_a_position_does_not_short():
    result = plan({"NVDA": "Sell"})
    assert result.intents == []


def test_sell_below_a_zero_target_would_not_short():
    # Guards the defensive branch in _sell_intent: even if a target somehow
    # goes negative, an unheld symbol must not become a short entry.
    policy = TargetWeightPolicy()
    policy.weights["Sell"] = -0.05  # bypasses constructor validation on purpose
    result = plan({"NVDA": "Sell"}, policy=policy)
    assert result.intents == []
    assert any("shorting" in note for note in result.skipped)


def test_delta_below_minimum_notional_is_skipped():
    # $7,995 held against an $8,000 target: a $5 rebalance is noise.
    result = plan(
        {"NVDA": "Buy"},
        positions=[position("NVDA", 79.95, 100.0)],
        min_order_notional=10.0,
    )
    assert result.intents == []
    assert any("below minimum order notional" in n for n in result.skipped)


def test_gross_exposure_cap_scales_down_buys_proportionally():
    ratings = {t: "Buy" for t in ("AAA", "BBB", "CCC", "DDD", "EEE")}
    # Five 8% targets want 40% gross; the cap allows 20%.
    result = plan(ratings, max_gross_exposure=0.20)
    total = sum(i.notional for i in result.intents)
    assert total == pytest.approx(20_000.0)
    assert len(result.intents) == 5
    assert all(i.notional == pytest.approx(4_000.0) for i in result.intents)


def test_untouched_positions_count_toward_the_gross_cap():
    # $15k already invested elsewhere leaves $5k of a 20% cap for the new buy.
    result = plan(
        {"NVDA": "Buy"},
        positions=[position("TSLA", 150, 100.0)],
        max_gross_exposure=0.20,
    )
    (intent,) = result.intents
    assert intent.notional == pytest.approx(5_000.0)


def test_gross_cap_never_blocks_a_sell():
    result = plan(
        {"NVDA": "Sell", "AMD": "Buy"},
        positions=[position("NVDA", 100, 100.0)],
        max_gross_exposure=0.05,
    )
    sells = [i for i in result.intents if i.side == SELL]
    assert len(sells) == 1
    assert sells[0].qty == pytest.approx(100.0)


def test_whole_share_mode_floors_the_buy_quantity():
    result = plan(
        {"NVDA": "Buy"},
        fractional_shares=False,
        price_lookup=lambda symbol: 300.0,
    )
    (intent,) = result.intents
    # $8,000 / $300 = 26.67 -> 26 whole shares.
    assert intent.qty == pytest.approx(26.0)
    assert intent.notional is None


def test_whole_share_mode_without_a_price_skips_the_order():
    result = plan({"NVDA": "Buy"}, fractional_shares=False, price_lookup=lambda s: None)
    assert result.intents == []
    assert any("needs a price" in n for n in result.skipped)


def test_zero_equity_plans_nothing():
    result = plan({"NVDA": "Buy"}, equity=0.0)
    assert result.intents == []
    assert any("equity" in n for n in result.skipped)


def test_invalid_ticker_is_rejected_before_it_reaches_a_path():
    with pytest.raises(ValueError):
        plan({"../../etc/passwd": "Buy"})


def test_client_order_id_is_stable_and_input_sensitive():
    base = client_order_id("NVDA", TRADE_DATE, "Buy", BUY)
    assert base == client_order_id("NVDA", TRADE_DATE, "Buy", BUY)
    assert base.startswith("ta-")
    assert len(base) <= 128
    assert base != client_order_id("NVDA", "2026-08-08", "Buy", BUY)
    assert base != client_order_id("NVDA", TRADE_DATE, "Overweight", BUY)
    assert base != client_order_id("AMD", TRADE_DATE, "Buy", BUY)
