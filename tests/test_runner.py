"""Tests for the watchlist, run history, and the analyse-then-execute cycle."""

from __future__ import annotations

import threading

import pytest

from tests.execution_fakes import FakeBroker, position
from tradingagents.execution import ExecutionEngine
from tradingagents.runner import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_HALTED,
    RunHistory,
    RunRecord,
    RunnerBusy,
    TradingRunner,
    Watchlist,
)

TRADE_DATE = "2026-08-07"


class FakeGraph:
    """Stands in for TradingAgentsGraph: returns canned ratings, no LLM calls."""

    def __init__(self, ratings=None, fail_on=()):
        self.ratings = ratings or {}
        self.fail_on = set(fail_on)
        self.calls = []

    def propagate(self, ticker, trade_date):
        self.calls.append((ticker, trade_date))
        if ticker in self.fail_on:
            raise RuntimeError(f"analysis blew up for {ticker}")
        rating = self.ratings.get(ticker, "Hold")
        return {"final_trade_decision": f"**Rating**: {rating}"}, rating


def make_runner(tmp_path, graph=None, broker=None, **config_overrides):
    config = {
        "data_cache_dir": str(tmp_path / "cache"),
        "execution_enabled": True,
        "execution_dry_run": False,
        "run_max_tickers": 10,
    }
    config.update(config_overrides)
    broker = broker or FakeBroker()
    engine = ExecutionEngine(config, broker=broker)
    return TradingRunner(
        config,
        broker=broker,
        engine=engine,
        graph=graph or FakeGraph(),
    )


# ---- watchlist -------------------------------------------------------


def test_watchlist_round_trips(tmp_path):
    watchlist = Watchlist(tmp_path / "watchlist.json")
    assert watchlist.load() == []
    watchlist.save(["nvda", "amd"])
    assert watchlist.load() == ["NVDA", "AMD"]


def test_watchlist_deduplicates_and_preserves_order(tmp_path):
    watchlist = Watchlist(tmp_path / "watchlist.json")
    assert watchlist.save(["NVDA", "amd", "NVDA", " TSLA "]) == ["NVDA", "AMD", "TSLA"]


def test_watchlist_rejects_a_path_traversal_ticker(tmp_path):
    watchlist = Watchlist(tmp_path / "watchlist.json")
    with pytest.raises(ValueError):
        watchlist.save(["../../etc/passwd"])


def test_watchlist_add_and_remove(tmp_path):
    watchlist = Watchlist(tmp_path / "watchlist.json")
    watchlist.save(["NVDA"])
    assert watchlist.add("amd") == ["NVDA", "AMD"]
    assert watchlist.remove("nvda") == ["AMD"]


def test_unreadable_watchlist_reads_as_empty(tmp_path):
    path = tmp_path / "watchlist.json"
    path.write_text("{broken", encoding="utf-8")
    assert Watchlist(path).load() == []


# ---- run history -----------------------------------------------------


def test_history_save_replaces_by_run_id(tmp_path):
    history = RunHistory(tmp_path / "runs.jsonl")
    record = RunRecord(
        run_id="run-1", trigger="manual", trade_date=TRADE_DATE, started_at="now"
    )
    history.save(record)
    record.status = STATUS_COMPLETED
    history.save(record)
    assert len(history.all()) == 1
    assert history.get("run-1")["status"] == STATUS_COMPLETED


def test_history_recent_is_newest_first(tmp_path):
    history = RunHistory(tmp_path / "runs.jsonl")
    for i in range(3):
        history.save(
            RunRecord(
                run_id=f"run-{i}", trigger="manual", trade_date=TRADE_DATE, started_at="now"
            )
        )
    assert [r["run_id"] for r in history.recent()] == ["run-2", "run-1", "run-0"]


def test_history_is_trimmed_to_max_records(tmp_path):
    history = RunHistory(tmp_path / "runs.jsonl", max_records=2)
    for i in range(5):
        history.save(
            RunRecord(
                run_id=f"run-{i}", trigger="manual", trade_date=TRADE_DATE, started_at="now"
            )
        )
    assert [r["run_id"] for r in history.all()] == ["run-3", "run-4"]


# ---- the cycle -------------------------------------------------------


def test_run_analyses_every_ticker_then_executes_once(tmp_path):
    graph = FakeGraph({"NVDA": "Buy", "AMD": "Sell"})
    broker = FakeBroker(positions=[position("AMD", 20, 50.0)])
    runner = make_runner(tmp_path, graph=graph, broker=broker)

    record = runner.run_once(["NVDA", "AMD"], trade_date=TRADE_DATE)

    assert record.status == STATUS_COMPLETED
    assert record.ratings == {"NVDA": "Buy", "AMD": "Sell"}
    assert [c[0] for c in graph.calls] == ["NVDA", "AMD"]
    # Both orders come from a single execute_ratings call, so the gross cap
    # saw the whole book at once.
    assert {o["symbol"] for o in record.orders} == {"NVDA", "AMD"}


def test_run_defaults_to_the_watchlist(tmp_path):
    graph = FakeGraph({"NVDA": "Buy"})
    runner = make_runner(tmp_path, graph=graph)
    runner.watchlist.save(["NVDA"])
    record = runner.run_once(trade_date=TRADE_DATE)
    assert record.tickers == ["NVDA"]


def test_empty_watchlist_completes_without_analysis(tmp_path):
    graph = FakeGraph()
    runner = make_runner(tmp_path, graph=graph)
    record = runner.run_once(trade_date=TRADE_DATE)
    assert record.status == STATUS_COMPLETED
    assert graph.calls == []
    assert "empty" in record.note


def test_ticker_cap_truncates_and_says_so(tmp_path):
    runner = make_runner(tmp_path, graph=FakeGraph(), run_max_tickers=2)
    record = runner.run_once(["AAA", "BBB", "CCC"], trade_date=TRADE_DATE)
    assert record.tickers == ["AAA", "BBB"]
    assert "truncated" in record.note


def test_one_failing_ticker_does_not_abort_the_pass(tmp_path):
    graph = FakeGraph({"NVDA": "Buy", "AMD": "Buy"}, fail_on=["NVDA"])
    runner = make_runner(tmp_path, graph=graph)
    record = runner.run_once(["NVDA", "AMD"], trade_date=TRADE_DATE)
    assert record.status == STATUS_COMPLETED
    assert "NVDA" in record.errors
    assert record.ratings == {"AMD": "Buy"}


def test_halted_switch_skips_analysis_entirely(tmp_path):
    graph = FakeGraph({"NVDA": "Buy"})
    runner = make_runner(tmp_path, graph=graph)
    runner.kill_switch.halt("tripped before the run")

    record = runner.run_once(["NVDA"], trade_date=TRADE_DATE)
    assert record.status == STATUS_HALTED
    assert graph.calls == [], "a halted account must not spend money on LLM calls"
    assert "kill switch active" in record.note


def test_unreadable_equity_fails_closed(tmp_path):
    class BlindBroker(FakeBroker):
        def get_account(self):
            raise RuntimeError("alpaca unreachable")

    graph = FakeGraph({"NVDA": "Buy"})
    runner = make_runner(tmp_path, graph=graph, broker=BlindBroker())
    record = runner.run_once(["NVDA"], trade_date=TRADE_DATE)
    assert record.status == STATUS_HALTED
    assert graph.calls == []


def test_flatten_on_halt_closes_positions(tmp_path):
    broker = FakeBroker(positions=[position("NVDA", 10, 100.0)])
    runner = make_runner(
        tmp_path, graph=FakeGraph(), broker=broker, risk_flatten_on_halt=True
    )
    runner.kill_switch.halt("tripped")
    record = runner.run_once(["NVDA"], trade_date=TRADE_DATE)
    assert record.status == STATUS_HALTED
    assert "flattened 1 position(s): NVDA" in record.note
    assert [i.symbol for i in broker.submitted] == ["NVDA"]


def test_run_failure_is_recorded_not_raised(tmp_path):
    class BrokenHistory(RunHistory):
        def save(self, record):
            if record.ratings:
                raise RuntimeError("disk full")
            super().save(record)

    runner = make_runner(tmp_path, graph=FakeGraph({"NVDA": "Buy"}))
    runner.history = BrokenHistory(tmp_path / "runs.jsonl")
    record = runner.run_once(["NVDA"], trade_date=TRADE_DATE)
    assert record.status == STATUS_FAILED
    assert "disk full" in record.note


def test_concurrent_runs_are_refused(tmp_path):
    started = threading.Event()
    release = threading.Event()

    class BlockingGraph(FakeGraph):
        def propagate(self, ticker, trade_date):
            started.set()
            release.wait(timeout=5)
            return super().propagate(ticker, trade_date)

    runner = make_runner(tmp_path, graph=BlockingGraph({"NVDA": "Buy"}))
    thread = threading.Thread(
        target=runner.run_once, args=(["NVDA"],), kwargs={"trade_date": TRADE_DATE}
    )
    thread.start()
    try:
        assert started.wait(timeout=5)
        assert runner.is_running is True
        with pytest.raises(RunnerBusy):
            runner.run_once(["AMD"], trade_date=TRADE_DATE)
    finally:
        release.set()
        thread.join(timeout=5)

    assert runner.is_running is False


def test_status_reports_the_operating_mode(tmp_path):
    runner = make_runner(tmp_path, graph=FakeGraph())
    runner.watchlist.save(["NVDA"])
    status = runner.status()
    assert status["watchlist"] == ["NVDA"]
    assert status["execution_enabled"] is True
    assert status["execution_dry_run"] is False
    assert status["running"] is False
