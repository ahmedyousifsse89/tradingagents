"""Append-only record of every order intent the engine has produced.

The journal is the local half of idempotency (the broker's ``client_order_id``
is the other half) and the only durable record of what a dry run *would* have
done. It is written as JSON Lines so a crash mid-write can at worst lose the
final line rather than corrupt earlier history.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Set

logger = logging.getLogger(__name__)


class ExecutionJournal:
    """Read/append the execution journal at ``path``."""

    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)

    def append(self, record: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entry = dict(record)
        entry.setdefault("logged_at", datetime.now(timezone.utc).isoformat())
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def entries(self) -> List[dict]:
        if not self.path.exists():
            return []
        rows: List[dict] = []
        for line_no, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                # A torn final line from an interrupted write must not make
                # the whole journal unreadable — the guard needs it to work.
                logger.warning("skipping unparseable journal line %d in %s", line_no, self.path)
        return rows

    def submitted_client_order_ids(self) -> Set[str]:
        """Client order ids that reached the broker. Dry runs are excluded."""
        return {
            e["client_order_id"]
            for e in self.entries()
            if e.get("submitted") and e.get("client_order_id")
        }

    def submitted_count_on(self, day: str) -> int:
        """Number of orders actually submitted on calendar day ``day`` (UTC).

        ``day`` is an ISO date string; the count is over the journal's own
        ``logged_at`` wall-clock, not the trade date, because the cap exists
        to bound damage from a runaway loop in real time.
        """
        total = 0
        for entry in self.entries():
            if not entry.get("submitted"):
                continue
            logged_at = entry.get("logged_at", "")
            if logged_at[:10] == day:
                total += 1
        return total

    def records_for(self, client_order_id: str) -> Iterable[dict]:
        return (
            e for e in self.entries() if e.get("client_order_id") == client_order_id
        )


def default_journal_path(config: dict) -> Optional[str]:
    """Journal location from config, defaulting under the data cache dir."""
    configured = config.get("execution_journal_path")
    if configured:
        return configured
    cache_dir = config.get("data_cache_dir")
    if not cache_dir:
        return None
    return os.path.join(cache_dir, "execution", "journal.jsonl")
