"""Find the price a decision actually executed at.

The reflection layer grades past decisions so future runs can learn from them.
Grading against the closing price on the analysis date measures a trade nobody
made: the real order filled at the next session's open, at a price that
included slippage, and sometimes did not fill at all because a guard rejected
it or the rating was Hold.

This module answers "what did the account actually pay for the decision made
on date D for ticker T?" by joining the execution journal (which knows the
deterministic ``client_order_id`` for every intent) to the broker (which knows
what filled). ``None`` means no actual execution — the caller then falls back
to a market-price estimate and labels it as hypothetical, rather than quietly
presenting one as the other.
"""

from __future__ import annotations

import logging
from typing import Optional

from .broker import BUY, FillInfo
from .journal import ExecutionJournal

logger = logging.getLogger(__name__)


class EntryFillLookup:
    """Resolve the entry fill for a (ticker, trade_date) decision."""

    def __init__(self, journal: ExecutionJournal, broker):
        self.journal = journal
        self.broker = broker

    def find(self, ticker: str, trade_date: str) -> Optional[FillInfo]:
        """Fill for the buy placed on ``trade_date`` for ``ticker``, if any.

        Only buys count as an entry. A decision whose order was a sell is an
        exit of an earlier entry, and grading it against its own fill price
        would measure nothing.
        """
        symbol = ticker.upper()
        candidates = [
            entry
            for entry in self.journal.entries()
            if entry.get("submitted")
            and entry.get("side") == BUY
            and str(entry.get("symbol", "")).upper() == symbol
            and str(entry.get("trade_date", "")) == str(trade_date)
        ]
        if not candidates:
            return None

        # Most recent wins: a re-run that legitimately placed a second order
        # for the same date means the later one is the live entry.
        for entry in reversed(candidates):
            client_order_id = entry.get("client_order_id")
            if not client_order_id:
                continue
            try:
                fill = self.broker.get_fill(client_order_id)
            except Exception:
                logger.debug("fill lookup raised for %s", client_order_id)
                continue
            if fill is not None and fill.price > 0:
                return fill
        return None

    def __call__(self, ticker: str, trade_date: str) -> Optional[FillInfo]:
        return self.find(ticker, trade_date)


def entry_fill_lookup(config: dict, broker) -> Optional[EntryFillLookup]:
    """Build a lookup from config, or None when no journal path resolves."""
    from .journal import default_journal_path

    path = default_journal_path(config)
    if path is None or broker is None:
        return None
    return EntryFillLookup(ExecutionJournal(path), broker)
