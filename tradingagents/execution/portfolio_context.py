"""Render live broker state into prompt text for the decision agents.

Without this, the Trader and Portfolio Manager reason about a ticker with no
idea whether the book already holds it. That produces the two failure modes
this module exists to prevent: recommending Buy on a name already at its
maximum weight, and recommending Sell on a name that is not held at all.

The rendered text is advisory only. It never changes order sizing — the
reconciler owns that, from broker data, arithmetically. Its purpose is to let
an agent say "already at target, Hold" instead of "Buy" and have that be the
informed answer rather than a coincidence.
"""

from __future__ import annotations

from typing import Optional, Sequence

from .broker import AccountSnapshot, PositionSnapshot


def render_portfolio_context(
    account: Optional[AccountSnapshot],
    positions: Sequence[PositionSnapshot],
    *,
    ticker: str,
    target_weights: Optional[dict] = None,
    max_position_weight: Optional[float] = None,
) -> str:
    """Describe the current book, foregrounding ``ticker``.

    Returns an empty string when there is no account to describe, so callers
    can drop the whole section from the prompt rather than render a
    misleading "no positions" when the truth is "the broker was unreachable".
    """
    if account is None or account.equity <= 0:
        return ""

    ticker = ticker.upper()
    by_symbol = {p.symbol.upper(): p for p in positions}
    held = by_symbol.get(ticker)

    lines = [
        f"- Account equity: ${account.equity:,.2f}",
        f"- Cash available: ${account.cash:,.2f}",
    ]

    invested = sum(p.market_value for p in positions)
    lines.append(
        f"- Invested: ${invested:,.2f} "
        f"({invested / account.equity:.1%} of equity) across {len(positions)} position(s)"
    )

    if held is not None:
        weight = held.market_value / account.equity
        lines.append(
            f"- Current {ticker} position: {held.qty:g} shares, "
            f"${held.market_value:,.2f} ({weight:.1%} of equity), "
            f"average entry ${held.avg_entry_price:,.2f}"
        )
        if max_position_weight is not None and weight >= max_position_weight:
            lines.append(
                f"- {ticker} is already at or above the {max_position_weight:.0%} "
                f"per-position cap; a more bullish rating cannot add exposure."
            )
    else:
        lines.append(f"- Current {ticker} position: none (flat)")
        lines.append(
            f"- A Sell or Underweight rating on {ticker} will place no order, "
            f"since shorting is not supported."
        )

    if target_weights:
        mapping = ", ".join(
            f"{rating} {weight:.0%}" if weight is not None else f"{rating} unchanged"
            for rating, weight in target_weights.items()
        )
        lines.append(f"- Your rating maps to a target weight: {mapping}.")

    others = [p for p in positions if p.symbol.upper() != ticker]
    if others:
        top = sorted(others, key=lambda p: p.market_value, reverse=True)[:5]
        summary = ", ".join(
            f"{p.symbol} {p.market_value / account.equity:.1%}" for p in top
        )
        lines.append(f"- Other holdings: {summary}")

    return "\n".join(lines)


def fetch_portfolio_context(
    broker,
    ticker: str,
    *,
    target_weights: Optional[dict] = None,
    max_position_weight: Optional[float] = None,
) -> str:
    """Read live state from ``broker`` and render it; empty string on failure.

    A broker outage must degrade the prompt, not abort the analysis: the run
    still produces a rating, and the execution layer will refuse to act on
    stale assumptions because it re-reads positions at order time anyway.
    """
    try:
        account = broker.get_account()
        positions = list(broker.get_positions())
    except Exception:
        return ""
    return render_portfolio_context(
        account,
        positions,
        ticker=ticker,
        target_weights=target_weights,
        max_position_weight=max_position_weight,
    )
