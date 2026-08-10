"""Tests for the pre-submission order guard and the execution journal."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tradingagents.execution.broker import BUY, SELL, AccountSnapshot, OrderIntent
from tradingagents.execution.guard import OrderGuard
from tradingagents.execution.journal import ExecutionJournal, default_journal_path

NOW = datetime(2026, 8, 7, 15, 0, tzinfo=timezone.utc)
ACCOUNT = AccountSnapshot(equity=100_000.0, cash=50_000.0, buying_power=100_000.0)


def buy_intent(notional=1_000.0, client_order_id="ta-abc"):
    return OrderIntent(
        symbol="NVDA",
        side=BUY,
        client_order_id=client_order_id,
        reason="test",
        notional=notional,
        rating="Buy",
        trade_date="2026-08-07",
        current_value=0.0,
        target_value=notional,
    )


def sell_intent(current_value=5_000.0, target_value=0.0):
    return OrderIntent(
        symbol="NVDA",
        side=SELL,
        client_order_id="ta-sell",
        reason="test",
        qty=50.0,
        rating="Sell",
        trade_date="2026-08-07",
        current_value=current_value,
        target_value=target_value,
    )


@pytest.fixture()
def guard(tmp_path):
    return OrderGuard(ExecutionJournal(tmp_path / "journal.jsonl"))


def test_clean_order_passes(guard):
    assert guard.reject_reason(buy_intent(), ACCOUNT, market_open=True, now=NOW) is None


def test_blocked_account_is_rejected(guard):
    blocked = AccountSnapshot(
        equity=100_000.0, cash=0.0, buying_power=0.0, trading_blocked=True
    )
    reason = guard.reject_reason(buy_intent(), blocked, market_open=True, now=NOW)
    assert "trading_blocked" in reason


def test_closed_market_is_rejected(guard):
    reason = guard.reject_reason(buy_intent(), ACCOUNT, market_open=False, now=NOW)
    assert "market is closed" in reason


def test_closed_market_allowed_when_configured(tmp_path):
    guard = OrderGuard(
        ExecutionJournal(tmp_path / "journal.jsonl"), allow_when_market_closed=True
    )
    assert guard.reject_reason(buy_intent(), ACCOUNT, market_open=False, now=NOW) is None


def test_order_below_minimum_notional_is_rejected(guard):
    reason = guard.reject_reason(buy_intent(notional=2.0), ACCOUNT, True, now=NOW)
    assert "below minimum" in reason


def test_order_above_per_order_cap_is_rejected(guard):
    # Cap defaults to 10% of $100k equity.
    reason = guard.reject_reason(buy_intent(notional=25_000.0), ACCOUNT, True, now=NOW)
    assert "exceeds per-order cap" in reason


def test_oversized_exit_is_allowed(guard):
    # A position that drifted above the per-position cap is exactly the one
    # whose exit trips a size cap. Blocking it would trap the account in the
    # position the cap exists to prevent.
    assert (
        guard.reject_reason(sell_intent(current_value=90_000.0), ACCOUNT, True, now=NOW)
        is None
    )


def test_daily_order_cap_does_not_block_exits(tmp_path):
    journal = ExecutionJournal(tmp_path / "journal.jsonl")
    guard = OrderGuard(journal, max_orders_per_day=1)
    journal.append(
        {
            "client_order_id": "ta-0",
            "submitted": True,
            "logged_at": "2026-08-07T10:00:00+00:00",
        }
    )
    assert guard.reject_reason(buy_intent(), ACCOUNT, True, now=NOW) is not None
    assert guard.reject_reason(sell_intent(), ACCOUNT, True, now=NOW) is None


def test_exits_are_still_blocked_by_a_blocked_account(guard):
    blocked = AccountSnapshot(
        equity=100_000.0, cash=0.0, buying_power=0.0, trading_blocked=True
    )
    assert guard.reject_reason(sell_intent(), blocked, True, now=NOW) is not None


def test_exits_are_still_blocked_when_the_market_is_closed(guard):
    assert guard.reject_reason(sell_intent(), ACCOUNT, False, now=NOW) is not None


def test_dust_sized_exits_are_still_skipped(guard):
    reason = guard.reject_reason(
        sell_intent(current_value=5.0), ACCOUNT, True, now=NOW
    )
    assert "below minimum" in reason


def test_daily_order_cap_is_enforced(tmp_path):
    journal = ExecutionJournal(tmp_path / "journal.jsonl")
    guard = OrderGuard(journal, max_orders_per_day=2)
    for i in range(2):
        journal.append(
            {
                "client_order_id": f"ta-{i}",
                "submitted": True,
                "logged_at": "2026-08-07T10:00:00+00:00",
            }
        )
    reason = guard.reject_reason(buy_intent(), ACCOUNT, True, now=NOW)
    assert "daily order cap reached" in reason


def test_dry_run_entries_do_not_count_toward_the_daily_cap(tmp_path):
    journal = ExecutionJournal(tmp_path / "journal.jsonl")
    guard = OrderGuard(journal, max_orders_per_day=1)
    journal.append(
        {
            "client_order_id": "ta-dry",
            "submitted": False,
            "logged_at": "2026-08-07T10:00:00+00:00",
        }
    )
    assert guard.reject_reason(buy_intent(), ACCOUNT, True, now=NOW) is None


def test_duplicate_client_order_id_is_detected(tmp_path):
    journal = ExecutionJournal(tmp_path / "journal.jsonl")
    guard = OrderGuard(journal)
    journal.append({"client_order_id": "ta-abc", "submitted": True})
    assert "already submitted" in guard.duplicate_reason(buy_intent())


def test_dry_run_entry_is_not_treated_as_a_duplicate(tmp_path):
    journal = ExecutionJournal(tmp_path / "journal.jsonl")
    guard = OrderGuard(journal)
    journal.append({"client_order_id": "ta-abc", "submitted": False})
    assert guard.duplicate_reason(buy_intent()) is None


def test_journal_survives_a_torn_line(tmp_path):
    path = tmp_path / "journal.jsonl"
    journal = ExecutionJournal(path)
    journal.append({"client_order_id": "ta-1", "submitted": True})
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"client_order_id": "ta-2", "submi')  # interrupted write
    assert journal.submitted_client_order_ids() == {"ta-1"}


def test_journal_append_stamps_logged_at(tmp_path):
    journal = ExecutionJournal(tmp_path / "nested" / "journal.jsonl")
    journal.append({"client_order_id": "ta-1", "submitted": True})
    (entry,) = journal.entries()
    assert entry["logged_at"]


def test_default_journal_path_falls_under_the_cache_dir():
    path = default_journal_path({"data_cache_dir": "/cache"})
    assert path == "/cache/execution/journal.jsonl"


def test_explicit_journal_path_wins():
    path = default_journal_path(
        {"data_cache_dir": "/cache", "execution_journal_path": "/elsewhere/j.jsonl"}
    )
    assert path == "/elsewhere/j.jsonl"
