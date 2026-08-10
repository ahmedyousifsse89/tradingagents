"""Show the orders a set of ratings would produce, without placing any.

Reads live account and position state from Alpaca, plans orders against the
configured target weights, applies every guard, and prints the result. The
engine is forced into dry-run mode here regardless of config, so this script
cannot submit an order.

Ratings are supplied on the command line rather than produced by the agent
pipeline, which keeps the script free and instant — use it to sanity-check
sizing, caps, and reconciliation before wiring it to `propagate()`.

Usage:
    ALPACA_API_KEY_ID=... ALPACA_API_SECRET_KEY=... \
        python scripts/dry_run_execution.py NVDA=Buy AMD=Overweight TSLA=Sell

    # against the live account's real positions (still submits nothing).
    # Touching the live endpoint at all requires TRADINGAGENTS_ALPACA_ALLOW_LIVE.
    ... python scripts/dry_run_execution.py --live-data NVDA=Buy
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from tradingagents.agents.utils.rating import RATINGS_5_TIER
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.execution import ExecutionEngine, describe_results


def parse_ratings(pairs: list[str]) -> dict[str, str]:
    ratings: dict[str, str] = {}
    valid = {r.lower(): r for r in RATINGS_5_TIER}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"expected TICKER=Rating, got {pair!r}")
        ticker, _, rating = pair.partition("=")
        canonical = valid.get(rating.strip().lower())
        if canonical is None:
            raise SystemExit(
                f"unknown rating {rating!r}; expected one of {', '.join(RATINGS_5_TIER)}"
            )
        ratings[ticker.strip().upper()] = canonical
    return ratings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ratings", nargs="+", metavar="TICKER=RATING")
    parser.add_argument(
        "--trade-date",
        default=date.today().isoformat(),
        help="date stamped on the order intents (default: today)",
    )
    parser.add_argument(
        "--live-data",
        action="store_true",
        help="read positions from the live account instead of paper; still submits nothing",
    )
    args = parser.parse_args()

    config = DEFAULT_CONFIG.copy()
    config["execution_dry_run"] = True
    config["execution_enabled"] = False
    config["alpaca_live"] = args.live_data

    engine = ExecutionEngine(config)
    ratings = parse_ratings(args.ratings)

    plan = engine.plan(ratings, trade_date=args.trade_date)
    print(
        f"equity ${plan.account.equity:,.2f}  "
        f"cash ${plan.account.cash:,.2f}  "
        f"positions {len(plan.positions)}"
    )
    for note in plan.skipped:
        print(f"  skipped: {note}")

    results = engine.execute_ratings(ratings, trade_date=args.trade_date)
    print(describe_results(results))
    print(f"\njournalled to {engine.journal.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
