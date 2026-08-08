"""The set of tickers the scheduled runner analyses.

Stored as a small JSON file rather than in config so the dashboard can edit it
at runtime without a redeploy. Every ticker is validated on the way in — the
same validation the cache paths use — because these strings reach the broker,
the filesystem, and the LLM tool layer.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from tradingagents.dataflows.utils import safe_ticker_component


class Watchlist:
    """A de-duplicated, ordered list of tickers persisted to ``path``."""

    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)

    def load(self) -> List[str]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        tickers = raw.get("tickers", []) if isinstance(raw, dict) else raw
        return [t for t in tickers if isinstance(t, str)]

    def save(self, tickers: Iterable[str]) -> List[str]:
        cleaned = self._clean(tickers)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tickers": cleaned,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
        return cleaned

    def add(self, ticker: str) -> List[str]:
        return self.save([*self.load(), ticker])

    def remove(self, ticker: str) -> List[str]:
        target = ticker.strip().upper()
        return self.save([t for t in self.load() if t.upper() != target])

    @staticmethod
    def _clean(tickers: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        cleaned: List[str] = []
        for ticker in tickers:
            if not isinstance(ticker, str):
                continue
            candidate = safe_ticker_component(ticker.strip().upper())
            if candidate in seen:
                continue
            seen.add(candidate)
            cleaned.append(candidate)
        return cleaned


def default_watchlist_path(config: dict) -> Optional[str]:
    configured = config.get("watchlist_path")
    if configured:
        return configured
    cache_dir = config.get("data_cache_dir")
    if not cache_dir:
        return None
    return os.path.join(cache_dir, "watchlist.json")
