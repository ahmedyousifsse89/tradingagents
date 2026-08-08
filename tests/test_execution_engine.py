"""Tests for the execution engine: gating, dry run, journalling, idempotency."""

from __future__ import annotations

import pytest

from tests.execution_fakes import FakeBroker, position
from tradingagents.execution import (
    STATUS_DRY_RUN,
    STATUS_DUPLICATE,
    STATUS_ERROR,
    STATUS_REJECTED,
    STATUS_SUBMITTED,
    ExecutionDisabled,
    ExecutionEngine,
    describe_results,
)

TRADE_DATE = "2026-08-07"


def make_config(tmp_path, **overrides):
    config = {
        "data_cache_dir": str(tmp_path / "cache"),
        "execution_enabled": True,
        "execution_dry_run": False,
        "execution_target_weights": {
            "Buy": 0.08,
            "Overweight": 0.04,
            "Hold": None,
            "Underweight": 0.02,
            "Sell": 0.0,
        },
        "execution_max_position_weight": 0.10,
        "execution_max_gross_exposure": 0.80,
        "execution_min_order_notional": 10.0,
        "execution_max_orders_per_day": 20,
        "execution_fractional_shares": True,
        "execution_allow_when_market_closed": False,
    }
    config.update(overrides)
    return config


def test_defaults_are_dry_run_and_disabled(tmp_path):
    engine = ExecutionEngine(
        {"data_cache_dir": str(tmp_path)}, broker=FakeBroker()
    )
    assert engine.dry_run is True
    assert engine.enabled is False


def test_dry_run_plans_but_submits_nothing(tmp_path):
    broker = FakeBroker()
    engine = ExecutionEngine(
        make_config(tmp_path, execution_dry_run=True), broker=broker
    )
    (result,) = engine.execute_ratings({"NVDA": "Buy"}, trade_date=TRADE_DATE)
    assert result.status == STATUS_DRY_RUN
    assert result.submitted is False
    assert result.intent.notional == pytest.approx(8_000.0)
    assert broker.submitted == []


def test_submission_requires_the_master_switch(tmp_path):
    engine = ExecutionEngine(
        make_config(tmp_path, execution_enabled=False, execution_dry_run=False),
        broker=FakeBroker(),
    )
    with pytest.raises(ExecutionDisabled, match="execution_enabled is not set"):
        engine.execute_ratings({"NVDA": "Buy"}, trade_date=TRADE_DATE)


def test_live_path_submits_and_journals(tmp_path):
    broker = FakeBroker()
    engine = ExecutionEngine(make_config(tmp_path), broker=broker)
    (result,) = engine.execute_ratings({"NVDA": "Buy"}, trade_date=TRADE_DATE)
    assert result.status == STATUS_SUBMITTED
    assert result.submitted is True
    assert [i.symbol for i in broker.submitted] == ["NVDA"]

    (entry,) = engine.journal.entries()
    assert entry["symbol"] == "NVDA"
    assert entry["submitted"] is True
    assert entry["broker_order_id"] == "order-1"
    assert entry["rating"] == "Buy"


def test_rerunning_the_same_rating_does_not_double_the_order(tmp_path):
    broker = FakeBroker()
    engine = ExecutionEngine(make_config(tmp_path), broker=broker)
    engine.execute_ratings({"NVDA": "Buy"}, trade_date=TRADE_DATE)

    # Second run, before the fill shows up in positions: the journal's
    # client_order_id record is what stops a duplicate order.
    (result,) = engine.execute_ratings({"NVDA": "Buy"}, trade_date=TRADE_DATE)
    assert result.status == STATUS_DUPLICATE
    assert len(broker.submitted) == 1


def test_broker_side_duplicate_is_caught_when_the_journal_is_lost(tmp_path):
    broker = FakeBroker()
    engine = ExecutionEngine(make_config(tmp_path), broker=broker)
    engine.execute_ratings({"NVDA": "Buy"}, trade_date=TRADE_DATE)
    engine.journal.path.unlink()

    (result,) = engine.execute_ratings({"NVDA": "Buy"}, trade_date=TRADE_DATE)
    assert result.status == STATUS_DUPLICATE
    assert "broker already holds" in result.detail
    assert len(broker.submitted) == 1


def test_position_matching_target_yields_no_orders(tmp_path):
    broker = FakeBroker(positions=[position("NVDA", 80, 100.0)])
    engine = ExecutionEngine(make_config(tmp_path), broker=broker)
    assert engine.execute_ratings({"NVDA": "Buy"}, trade_date=TRADE_DATE) == []
    assert broker.submitted == []


def test_closed_market_rejects_without_submitting(tmp_path):
    broker = FakeBroker(market_open=False)
    engine = ExecutionEngine(make_config(tmp_path), broker=broker)
    (result,) = engine.execute_ratings({"NVDA": "Buy"}, trade_date=TRADE_DATE)
    assert result.status == STATUS_REJECTED
    assert broker.submitted == []


def test_guards_apply_identically_in_dry_run(tmp_path):
    # A dry run is only useful as evidence if it rejects what a live run
    # would reject.
    broker = FakeBroker(market_open=False)
    engine = ExecutionEngine(
        make_config(tmp_path, execution_dry_run=True), broker=broker
    )
    (result,) = engine.execute_ratings({"NVDA": "Buy"}, trade_date=TRADE_DATE)
    assert result.status == STATUS_REJECTED


def test_broker_failure_is_recorded_not_raised(tmp_path):
    class ExplodingBroker(FakeBroker):
        def submit(self, intent):
            from tradingagents.execution.broker import OrderResult

            return OrderResult(
                intent=intent,
                status=STATUS_ERROR,
                submitted=False,
                detail="RuntimeError: broker unavailable",
            )

    engine = ExecutionEngine(make_config(tmp_path), broker=ExplodingBroker())
    (result,) = engine.execute_ratings({"NVDA": "Buy"}, trade_date=TRADE_DATE)
    assert result.status == STATUS_ERROR
    assert result.submitted is False
    (entry,) = engine.journal.entries()
    assert entry["submitted"] is False


def test_multi_ticker_run_sells_and_buys_together(tmp_path):
    broker = FakeBroker(positions=[position("TSLA", 100, 100.0)])
    engine = ExecutionEngine(make_config(tmp_path), broker=broker)
    results = engine.execute_ratings(
        {"NVDA": "Buy", "TSLA": "Sell"}, trade_date=TRADE_DATE
    )
    by_symbol = {r.intent.symbol: r for r in results}
    assert by_symbol["NVDA"].intent.side == "buy"
    assert by_symbol["TSLA"].intent.side == "sell"
    assert by_symbol["TSLA"].intent.qty == pytest.approx(100.0)
    assert all(r.status == STATUS_SUBMITTED for r in results)


def test_execute_decision_wraps_a_single_ticker(tmp_path):
    engine = ExecutionEngine(
        make_config(tmp_path, execution_dry_run=True), broker=FakeBroker()
    )
    (result,) = engine.execute_decision("NVDA", "Buy", trade_date=TRADE_DATE)
    assert result.intent.symbol == "NVDA"


def test_describe_results_is_readable(tmp_path):
    engine = ExecutionEngine(
        make_config(tmp_path, execution_dry_run=True), broker=FakeBroker()
    )
    results = engine.execute_ratings({"NVDA": "Buy"}, trade_date=TRADE_DATE)
    text = describe_results(results)
    assert "BUY" in text and "NVDA" in text and "8,000.00" in text
    assert describe_results([]).startswith("No orders")


def test_missing_journal_path_is_rejected():
    with pytest.raises(ValueError, match="no journal path"):
        ExecutionEngine({"execution_enabled": True}, broker=FakeBroker())
