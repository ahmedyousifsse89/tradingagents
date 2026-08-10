"""Tests for the live-holdings block injected into agent prompts."""

from __future__ import annotations

from tests.execution_fakes import FakeBroker, position
from tradingagents.execution.broker import AccountSnapshot
from tradingagents.execution.portfolio_context import (
    fetch_portfolio_context,
    render_portfolio_context,
)
from tradingagents.execution.sizing import DEFAULT_TARGET_WEIGHTS

ACCOUNT = AccountSnapshot(equity=100_000.0, cash=40_000.0, buying_power=100_000.0)


def test_held_position_is_foregrounded():
    text = render_portfolio_context(
        ACCOUNT, [position("NVDA", 80, 100.0)], ticker="NVDA"
    )
    assert "Current NVDA position: 80 shares, $8,000.00 (8.0% of equity)" in text
    assert "Account equity: $100,000.00" in text


def test_flat_position_says_so_and_warns_about_shorting():
    text = render_portfolio_context(ACCOUNT, [], ticker="NVDA")
    assert "Current NVDA position: none (flat)" in text
    assert "shorting is not supported" in text


def test_position_at_the_cap_is_called_out():
    text = render_portfolio_context(
        ACCOUNT,
        [position("NVDA", 100, 100.0)],  # 10% of equity
        ticker="NVDA",
        max_position_weight=0.10,
    )
    assert "already at or above the 10% per-position cap" in text


def test_position_below_the_cap_is_not_called_out():
    text = render_portfolio_context(
        ACCOUNT, [position("NVDA", 50, 100.0)], ticker="NVDA", max_position_weight=0.10
    )
    assert "per-position cap" not in text


def test_other_holdings_are_summarised():
    text = render_portfolio_context(
        ACCOUNT,
        [position("NVDA", 80, 100.0), position("AMD", 100, 50.0)],
        ticker="NVDA",
    )
    assert "Other holdings: AMD 5.0%" in text


def test_target_weight_table_is_rendered():
    text = render_portfolio_context(
        ACCOUNT, [], ticker="NVDA", target_weights=DEFAULT_TARGET_WEIGHTS
    )
    assert "Buy 8%" in text
    assert "Hold unchanged" in text


def test_case_insensitive_symbol_match():
    text = render_portfolio_context(ACCOUNT, [position("NVDA", 10, 100.0)], ticker="nvda")
    assert "none (flat)" not in text


def test_no_account_renders_nothing():
    assert render_portfolio_context(None, [], ticker="NVDA") == ""


def test_zero_equity_renders_nothing():
    empty = AccountSnapshot(equity=0.0, cash=0.0, buying_power=0.0)
    assert render_portfolio_context(empty, [], ticker="NVDA") == ""


def test_fetch_reads_from_the_broker():
    broker = FakeBroker(positions=[position("NVDA", 10, 100.0)])
    text = fetch_portfolio_context(broker, "NVDA")
    assert "Current NVDA position: 10 shares" in text


def test_fetch_degrades_to_empty_on_broker_failure():
    class DeadBroker(FakeBroker):
        def get_account(self):
            raise RuntimeError("alpaca unreachable")

    # A broker outage must weaken the prompt, not abort the analysis.
    assert fetch_portfolio_context(DeadBroker(), "NVDA") == ""


def test_graph_injects_context_into_initial_state():
    from tradingagents.graph.propagation import Propagator

    state = Propagator().create_initial_state(
        "NVDA", "2026-08-07", portfolio_context="holdings go here"
    )
    assert state["portfolio_context"] == "holdings go here"


def test_graph_defaults_context_to_empty():
    from tradingagents.graph.propagation import Propagator

    assert Propagator().create_initial_state("NVDA", "2026-08-07")["portfolio_context"] == ""
