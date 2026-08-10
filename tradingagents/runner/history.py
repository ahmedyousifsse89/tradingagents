"""Persisted history of scheduled and manual runs.

The dashboard reads this to show what the bot did and why. Each record holds
the per-ticker ratings, the orders that resulted, and any error — enough to
reconstruct a run without re-reading the full agent transcripts, which live
separately under ``results_dir``.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_HALTED = "halted"


@dataclass
class RunRecord:
    """One pass of the runner over a set of tickers."""

    run_id: str
    trigger: str                       # "schedule" | "manual" | "api"
    trade_date: str
    started_at: str
    status: str = STATUS_RUNNING
    finished_at: str = ""
    tickers: List[str] = field(default_factory=list)
    ratings: Dict[str, str] = field(default_factory=dict)
    decisions: Dict[str, str] = field(default_factory=dict)
    orders: List[dict] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%S%f")


class RunHistory:
    """Append-and-update store for :class:`RunRecord`s, one JSON line each.

    Updates rewrite the file. Run volume is a handful per day, so the cost is
    irrelevant and the format stays trivially inspectable.
    """

    def __init__(self, path: str | os.PathLike, max_records: int = 500):
        self.path = Path(path)
        self.max_records = max_records

    def all(self) -> List[dict]:
        if not self.path.exists():
            return []
        records = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("skipping unparseable run-history line in %s", self.path)
        return records

    def recent(self, limit: int = 25) -> List[dict]:
        return list(reversed(self.all()))[:limit]

    def get(self, run_id: str) -> Optional[dict]:
        for record in self.all():
            if record.get("run_id") == run_id:
                return record
        return None

    def save(self, record: RunRecord) -> None:
        """Insert or replace ``record`` by run_id."""
        payload = record.to_dict()
        records = [r for r in self.all() if r.get("run_id") != record.run_id]
        records.append(payload)
        records = records[-self.max_records :]
        self._write(records)

    def _write(self, records: List[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        os.replace(tmp, self.path)


def default_history_path(config: Dict[str, Any]) -> Optional[str]:
    configured = config.get("run_history_path")
    if configured:
        return configured
    cache_dir = config.get("data_cache_dir")
    if not cache_dir:
        return None
    return os.path.join(cache_dir, "runs.jsonl")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
