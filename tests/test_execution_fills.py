"""Tests for grading past decisions against the price actually paid."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tests.execution_fakes import FakeBroker, position
from tradingagents.execution import ExecutionEngine, ExecutionJournal
from tradingagents.execution.broker import FillInfo
from tradingagents.execution.fills import EntryFillLookup, entry_fill_lookup
from tradingagents.graph.reflection import Reflector

TRADE_DATE = "2026-08-07"


def engine_with_fills(tmp_path, fill_price=105.0, **overrides):
    config = {
        "data_cache_dir": str(tmp_path / "cache"),
        "execution_enabled": True,
        "execution_dry_run": False,
    }
    config.update(overrides)
    broker = FakeBroker(fill_price=fill_price)
    return ExecutionEngine(config, broker=broker), broker, config


# ---- lookup ----------------------------------------------------------


def test_lookup_finds_the_fill_for_a_submitted_buy(tmp_path):
    engine, broker, config = engine_with_fills(tmp_path)
    engine.execute_ratings({"NVDA": "Buy"}, trade_date=TRADE_DATE)

    lookup = entry_fill_lookup(config, broker)
    fill = lookup("NVDA", TRADE_DATE)
    assert fill is not None
    assert fill.price == 105.0


def test_lookup_is_case_insensitive_on_the_ticker(tmp_path):
    engine, broker, config = engine_with_fills(tmp_path)
    engine.execute_ratings({"NVDA": "Buy"}, trade_date=TRADE_DATE)
    assert entry_fill_lookup(config, broker)("nvda", TRADE_DATE) is not None


def test_lookup_returns_none_for_a_different_date(tmp_path):
    engine, broker, config = engine_with_fills(tmp_path)
    engine.execute_ratings({"NVDA": "Buy"}, trade_date=TRADE_DATE)
    assert entry_fill_lookup(config, broker)("NVDA", "2026-08-08") is None


def test_dry_run_orders_are_not_treated_as_fills(tmp_path):
    engine, broker, config = engine_with_fills(tmp_path, execution_dry_run=True)
    engine.execute_ratings({"NVDA": "Buy"}, trade_date=TRADE_DATE)
    # Nothing executed, so there is no price the account actually paid.
    assert entry_fill_lookup(config, broker)("NVDA", TRADE_DATE) is None


def test_sells_are_not_entry_fills(tmp_path):
    config = {
        "data_cache_dir": str(tmp_path / "cache"),
        "execution_enabled": True,
        "execution_dry_run": False,
    }
    broker = FakeBroker(positions=[position("NVDA", 10, 100.0)], fill_price=99.0)
    engine = ExecutionEngine(config, broker=broker)
    engine.execute_ratings({"NVDA": "Sell"}, trade_date=TRADE_DATE)
    assert entry_fill_lookup(config, broker)("NVDA", TRADE_DATE) is None


def test_unfilled_order_yields_no_fill(tmp_path):
    # Submitted but never filled: the broker reports no fill price.
    engine, broker, config = engine_with_fills(tmp_path, fill_price=None)
    engine.execute_ratings({"NVDA": "Buy"}, trade_date=TRADE_DATE)
    assert entry_fill_lookup(config, broker)("NVDA", TRADE_DATE) is None


def test_broker_failure_during_lookup_is_swallowed(tmp_path):
    engine, broker, config = engine_with_fills(tmp_path)
    engine.execute_ratings({"NVDA": "Buy"}, trade_date=TRADE_DATE)

    class AngryBroker(FakeBroker):
        def get_fill(self, client_order_id):
            raise RuntimeError("alpaca unreachable")

    lookup = EntryFillLookup(engine.journal, AngryBroker())
    assert lookup("NVDA", TRADE_DATE) is None


def test_empty_journal_yields_no_fill(tmp_path):
    lookup = EntryFillLookup(ExecutionJournal(tmp_path / "journal.jsonl"), FakeBroker())
    assert lookup("NVDA", TRADE_DATE) is None


# ---- return measurement ----------------------------------------------


@pytest.fixture()
def graph_with_prices(monkeypatch):
    """A bare graph whose price history is fixed: stock 100 -> 110, bench flat."""
    import pandas as pd

    from tradingagents.graph import trading_graph as module

    series = {
        "NVDA": [100.0, 102.0, 104.0, 106.0, 108.0, 110.0],
        "SPY": [400.0] * 6,
    }

    def fake_ticker(symbol):
        ticker = MagicMock()
        ticker.history = lambda **kwargs: pd.DataFrame({"Close": series[symbol]})
        return ticker

    monkeypatch.setattr(module.yf, "Ticker", fake_ticker)
    return module.TradingAgentsGraph.__new__(module.TradingAgentsGraph)


def test_return_is_measured_from_the_actual_fill(graph_with_prices):
    """A fill worse than the analysis-date close must lower the graded return."""
    from_close, _, _ = graph_with_prices._fetch_returns("NVDA", TRADE_DATE)
    from_fill, _, _ = graph_with_prices._fetch_returns(
        "NVDA", TRADE_DATE, entry_price=105.0
    )

    assert from_close == pytest.approx((110.0 - 100.0) / 100.0)
    assert from_fill == pytest.approx((110.0 - 105.0) / 105.0)
    assert from_fill < from_close


def test_alpha_reflects_the_fill_basis_too(graph_with_prices):
    # The benchmark leg is close-to-close (flat here), so alpha moves with the
    # stock leg's basis.
    _, alpha_close, _ = graph_with_prices._fetch_returns("NVDA", TRADE_DATE)
    _, alpha_fill, _ = graph_with_prices._fetch_returns(
        "NVDA", TRADE_DATE, entry_price=105.0
    )
    assert alpha_fill < alpha_close


def test_zero_or_missing_entry_price_falls_back_to_the_close(graph_with_prices):
    baseline, _, _ = graph_with_prices._fetch_returns("NVDA", TRADE_DATE)
    assert graph_with_prices._fetch_returns("NVDA", TRADE_DATE, entry_price=0.0)[0] == baseline
    assert graph_with_prices._fetch_returns("NVDA", TRADE_DATE, entry_price=None)[0] == baseline


# ---- reflection prompt -----------------------------------------------


def _prompt_for(**kwargs) -> str:
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="reflection")
    Reflector(llm).reflect_on_final_decision(
        final_decision="**Rating**: Buy", raw_return=0.05, alpha_return=0.02, **kwargs
    )
    return llm.invoke.call_args[0][0][1][1]


def test_reflection_says_when_the_return_is_from_a_real_fill():
    prompt = _prompt_for(entry_price=105.0)
    assert "actual fill at $105.00" in prompt
    assert "slippage" in prompt


def test_reflection_flags_a_hypothetical_outcome():
    prompt = _prompt_for()
    assert "hypothetical" in prompt
    assert "Judge the directional call, not the execution." in prompt
