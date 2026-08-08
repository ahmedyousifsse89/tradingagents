"""Tests for the drawdown kill switch."""

from __future__ import annotations

import json

import pytest

from tests.execution_fakes import FakeBroker
from tradingagents.execution import STATUS_REJECTED, ExecutionEngine
from tradingagents.execution.risk import (
    HALT_DAILY_DRAWDOWN,
    HALT_MANUAL,
    HALT_TOTAL_DRAWDOWN,
    KillSwitch,
    kill_switch_from_config,
)


@pytest.fixture()
def switch(tmp_path):
    return KillSwitch(
        tmp_path / "risk.json", max_total_drawdown=0.15, max_daily_drawdown=0.05
    )


def test_first_reading_sets_the_marks(switch):
    state = switch.evaluate(100_000.0, today="2026-08-07")
    assert state.high_water_mark == 100_000.0
    assert state.day_open_equity == 100_000.0
    assert state.halted is False


def test_high_water_mark_ratchets_up_only(switch):
    switch.evaluate(100_000.0, today="2026-08-07")
    switch.evaluate(120_000.0, today="2026-08-07")
    state = switch.evaluate(110_000.0, today="2026-08-07")
    assert state.high_water_mark == 120_000.0


def test_total_drawdown_trips_the_switch(switch):
    switch.evaluate(100_000.0, today="2026-08-07")
    # 16% below the high-water mark, on a later day so the daily limit is
    # not what fires.
    state = switch.evaluate(84_000.0, today="2026-08-10")
    assert state.halted is True
    assert state.halt_reason == HALT_TOTAL_DRAWDOWN
    assert "high-water mark" in state.halt_detail


def test_drawdown_within_the_limit_does_not_trip(switch):
    switch.evaluate(100_000.0, today="2026-08-07")
    state = switch.evaluate(90_000.0, today="2026-08-10")
    assert state.halted is False


def test_daily_drawdown_trips_the_switch(switch):
    switch.evaluate(100_000.0, today="2026-08-07")
    state = switch.evaluate(94_000.0, today="2026-08-07")  # -6% intraday
    assert state.halted is True
    assert state.halt_reason == HALT_DAILY_DRAWDOWN


def test_new_day_resets_the_daily_reference(switch):
    switch.evaluate(100_000.0, today="2026-08-07")
    switch.evaluate(96_000.0, today="2026-08-08")  # new day: this is the open
    state = switch.evaluate(95_000.0, today="2026-08-08")  # ~1% off the open
    assert state.halted is False
    assert state.day_open_equity == 96_000.0


def test_disabled_limits_never_trip(tmp_path):
    switch = KillSwitch(
        tmp_path / "risk.json", max_total_drawdown=None, max_daily_drawdown=None
    )
    switch.evaluate(100_000.0, today="2026-08-07")
    assert switch.evaluate(1_000.0, today="2026-08-10").halted is False


def test_halt_persists_across_instances(tmp_path):
    path = tmp_path / "risk.json"
    KillSwitch(path).halt("testing")
    assert KillSwitch(path).load().halted is True


def test_a_tripped_switch_stays_tripped_when_equity_recovers(switch):
    switch.evaluate(100_000.0, today="2026-08-07")
    switch.evaluate(80_000.0, today="2026-08-10")
    state = switch.evaluate(100_000.0, today="2026-08-11")
    assert state.halted is True, "recovery must not silently re-enable trading"


def test_resume_clears_the_halt_and_rebases_the_marks(switch):
    switch.evaluate(100_000.0, today="2026-08-07")
    switch.evaluate(80_000.0, today="2026-08-10")
    state = switch.resume()
    assert state.halted is False
    # Rebasing prevents an immediate re-trip on the same drawdown.
    assert state.high_water_mark == 80_000.0
    assert switch.evaluate(80_000.0, today="2026-08-11").halted is False


def test_zero_equity_reading_leaves_the_marks_alone(switch):
    switch.evaluate(100_000.0, today="2026-08-07")
    state = switch.evaluate(0.0, today="2026-08-07")
    assert state.high_water_mark == 100_000.0
    assert state.halted is False


def test_corrupt_state_file_fails_closed(tmp_path):
    path = tmp_path / "risk.json"
    path.write_text("{not json", encoding="utf-8")
    state = KillSwitch(path).load()
    assert state.halted is True
    assert "corrupt" in state.halt_detail


def test_state_file_is_written_atomically(tmp_path):
    path = tmp_path / "risk.json"
    switch = KillSwitch(path)
    switch.evaluate(100_000.0, today="2026-08-07")
    assert json.loads(path.read_text(encoding="utf-8"))["high_water_mark"] == 100_000.0
    assert not path.with_suffix(".json.tmp").exists()


def test_status_reports_current_drawdowns(switch):
    switch.evaluate(100_000.0, today="2026-08-07")
    switch.evaluate(95_000.0, today="2026-08-08")
    status = switch.status()
    assert status["equity"] == 95_000.0
    assert status["high_water_mark"] == 100_000.0
    assert status["total_drawdown"] == pytest.approx(0.05)
    assert status["halted"] is False


def test_manual_halt_reason_is_recorded(switch):
    state = switch.halt("stopping for maintenance")
    assert state.halt_reason == HALT_MANUAL
    assert state.halt_detail == "stopping for maintenance"
    assert state.history[-1]["event"] == "halt"


def test_kill_switch_from_config_honours_the_disable_flag(tmp_path):
    config = {"data_cache_dir": str(tmp_path), "risk_kill_switch_enabled": False}
    assert kill_switch_from_config(config) is None


def test_kill_switch_from_config_reads_the_limits(tmp_path):
    config = {
        "data_cache_dir": str(tmp_path),
        "risk_max_total_drawdown": 0.25,
        "risk_max_daily_drawdown": 0.10,
    }
    switch = kill_switch_from_config(config)
    assert switch.max_total_drawdown == 0.25
    assert switch.max_daily_drawdown == 0.10


# ---- integration with the engine -------------------------------------


def engine_config(tmp_path, **overrides):
    config = {
        "data_cache_dir": str(tmp_path / "cache"),
        "execution_enabled": True,
        "execution_dry_run": False,
    }
    config.update(overrides)
    return config


def test_halted_switch_blocks_every_order(tmp_path):
    broker = FakeBroker()
    engine = ExecutionEngine(engine_config(tmp_path), broker=broker)
    engine.kill_switch.halt("blocked for the test")

    (result,) = engine.execute_ratings({"NVDA": "Buy"}, trade_date="2026-08-07")
    assert result.status == STATUS_REJECTED
    assert "kill switch active" in result.detail
    assert broker.submitted == []


def test_halt_also_blocks_in_dry_run(tmp_path):
    broker = FakeBroker()
    engine = ExecutionEngine(
        engine_config(tmp_path, execution_dry_run=True), broker=broker
    )
    engine.kill_switch.halt("blocked for the test")
    (result,) = engine.execute_ratings({"NVDA": "Buy"}, trade_date="2026-08-07")
    assert result.status == STATUS_REJECTED


def test_engine_trips_the_switch_on_a_drawdown(tmp_path):
    config = engine_config(tmp_path, risk_max_total_drawdown=0.10)
    engine = ExecutionEngine(config, broker=FakeBroker(equity=100_000.0))
    engine.execute_ratings({"NVDA": "Buy"}, trade_date="2026-08-07")

    # Equity collapses; the next pass must halt rather than trade.
    poorer = ExecutionEngine(config, broker=FakeBroker(equity=80_000.0))
    (result,) = poorer.execute_ratings({"AMD": "Buy"}, trade_date="2026-08-08")
    assert result.status == STATUS_REJECTED
    assert "kill switch active" in result.detail


def test_flatten_all_closes_every_position(tmp_path):
    from tests.execution_fakes import position

    broker = FakeBroker(
        positions=[position("NVDA", 10, 100.0), position("AMD", 5, 50.0)]
    )
    engine = ExecutionEngine(engine_config(tmp_path), broker=broker)
    results = engine.flatten_all(trade_date="2026-08-07")
    assert {r.intent.symbol for r in results} == {"NVDA", "AMD"}
    assert all(r.intent.side == "sell" for r in results)
    assert all(r.submitted for r in results)


def test_flatten_all_ignores_the_halt(tmp_path):
    from tests.execution_fakes import position

    broker = FakeBroker(positions=[position("NVDA", 10, 100.0)])
    engine = ExecutionEngine(engine_config(tmp_path), broker=broker)
    engine.kill_switch.halt("tripped")
    # Flattening exists precisely for the halted case, so it must still work.
    (result,) = engine.flatten_all(trade_date="2026-08-07")
    assert result.submitted is True


def test_flatten_all_respects_dry_run(tmp_path):
    from tests.execution_fakes import position

    broker = FakeBroker(positions=[position("NVDA", 10, 100.0)])
    engine = ExecutionEngine(
        engine_config(tmp_path, execution_dry_run=True), broker=broker
    )
    (result,) = engine.flatten_all(trade_date="2026-08-07")
    assert result.submitted is False
    assert broker.submitted == []
