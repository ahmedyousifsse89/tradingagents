"""Turn target weights into the smallest set of orders that reaches them.

Reconciliation is what makes the execution layer safe to re-run. The plan is
always computed from *current broker positions* versus *target weights*, so a
second run on the same day produces zero orders once the first run's fills
have settled — rather than doubling the position, which is what a naive
"rating says Buy, therefore buy" mapping would do.
"""

from __future__ import annotations

import hashlib
from typing import Callable, Dict, List, Optional, Sequence

from tradingagents.dataflows.utils import safe_ticker_component

from .broker import (
    BUY,
    SELL,
    AccountSnapshot,
    ExecutionPlan,
    OrderIntent,
    PositionSnapshot,
)
from .sizing import TargetWeightPolicy


def client_order_id(symbol: str, trade_date: str, rating: str, side: str) -> str:
    """Deterministic broker-side idempotency key.

    The same ticker + date + rating + side always produces the same id, so a
    re-run that survives the local journal check is still rejected by the
    broker as a duplicate client order id. Truncated to stay well inside
    Alpaca's 128-character limit while keeping collisions implausible.
    """
    raw = f"{symbol}|{trade_date}|{rating}|{side}".lower()
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"ta-{digest}"


def _scale_to_gross_cap(
    targets: Dict[str, float],
    current_values: Dict[str, float],
    untouched_gross: float,
    gross_cap: float,
) -> Dict[str, float]:
    """Shrink target *increases* proportionally to respect the gross cap.

    Reductions are never scaled: a cap breach must not be able to hold back a
    Sell. Only the part of each target that adds exposure is competing for the
    remaining headroom.
    """
    base = {s: min(targets[s], current_values.get(s, 0.0)) for s in targets}
    increase = {s: targets[s] - base[s] for s in targets}
    total_increase = sum(increase.values())
    if total_increase <= 0:
        return targets

    headroom = gross_cap - untouched_gross - sum(base.values())
    if total_increase <= headroom:
        return targets

    factor = max(0.0, headroom) / total_increase
    return {s: base[s] + increase[s] * factor for s in targets}


def plan_orders(
    ratings: Dict[str, str],
    account: AccountSnapshot,
    positions: Sequence[PositionSnapshot],
    policy: TargetWeightPolicy,
    *,
    trade_date: str,
    min_order_notional: float = 10.0,
    max_gross_exposure: float = 0.80,
    fractional_shares: bool = True,
    price_lookup: Optional[Callable[[str], Optional[float]]] = None,
) -> ExecutionPlan:
    """Build the order intents that move the book from current to target.

    ``ratings`` maps ticker to a 5-tier rating. Positions held in symbols that
    are absent from ``ratings`` are left untouched, but their market value
    still counts toward the gross-exposure cap.
    """
    skipped: List[str] = []

    if account.equity <= 0:
        return ExecutionPlan(
            account=account,
            positions=positions,
            skipped=[f"account equity is {account.equity}; nothing can be sized"],
        )

    by_symbol = {p.symbol: p for p in positions}
    current_values = {s: by_symbol[s].market_value for s in by_symbol}

    targets: Dict[str, float] = {}
    for symbol, rating in ratings.items():
        # Symbols reach here from CLI input or agent output; validate before
        # they are used as journal keys or interpolated into an order id.
        symbol = safe_ticker_component(symbol)
        current_value = current_values.get(symbol, 0.0)
        current_weight = current_value / account.equity
        targets[symbol] = policy.target_weight(rating, current_weight) * account.equity

    untouched_gross = sum(
        p.market_value for s, p in by_symbol.items() if s not in targets
    )
    capped = _scale_to_gross_cap(
        targets, current_values, untouched_gross, max_gross_exposure * account.equity
    )
    for symbol, target in capped.items():
        if target < targets[symbol] - 1e-9:
            skipped.append(
                f"{symbol}: target trimmed from {targets[symbol]:.2f} to {target:.2f} "
                f"by gross exposure cap of {max_gross_exposure:.0%}"
            )
    targets = capped

    intents: List[OrderIntent] = []
    for symbol, target_value in sorted(targets.items()):
        position = by_symbol.get(symbol)
        current_value = current_values.get(symbol, 0.0)
        delta = target_value - current_value
        rating = ratings[symbol]

        if abs(delta) < min_order_notional:
            skipped.append(
                f"{symbol}: delta {delta:+.2f} below minimum order notional "
                f"{min_order_notional:.2f}"
            )
            continue

        if delta > 0:
            intent = _buy_intent(
                symbol,
                rating,
                trade_date,
                delta,
                current_value,
                target_value,
                fractional_shares,
                position,
                price_lookup,
                skipped,
            )
        else:
            intent = _sell_intent(
                symbol,
                rating,
                trade_date,
                delta,
                current_value,
                target_value,
                fractional_shares,
                position,
                skipped,
            )

        if intent is not None:
            intents.append(intent)

    return ExecutionPlan(
        account=account, positions=positions, intents=intents, skipped=skipped
    )


def _buy_intent(
    symbol,
    rating,
    trade_date,
    delta,
    current_value,
    target_value,
    fractional_shares,
    position,
    price_lookup,
    skipped,
) -> Optional[OrderIntent]:
    reason = f"{rating}: raise exposure {current_value:.2f} -> {target_value:.2f}"

    if fractional_shares:
        return OrderIntent(
            symbol=symbol,
            side=BUY,
            client_order_id=client_order_id(symbol, trade_date, rating, BUY),
            reason=reason,
            notional=round(delta, 2),
            rating=rating,
            trade_date=trade_date,
            current_value=current_value,
            target_value=target_value,
        )

    price = position.current_price if position else None
    if not price and price_lookup is not None:
        price = price_lookup(symbol)
    if not price or price <= 0:
        skipped.append(
            f"{symbol}: whole-share mode needs a price and none was available"
        )
        return None

    qty = float(int(delta / price))
    if qty < 1:
        skipped.append(
            f"{symbol}: whole-share mode rounds {delta:.2f} at {price:.2f} down to 0 shares"
        )
        return None

    return OrderIntent(
        symbol=symbol,
        side=BUY,
        client_order_id=client_order_id(symbol, trade_date, rating, BUY),
        reason=reason,
        qty=qty,
        rating=rating,
        trade_date=trade_date,
        current_value=current_value,
        target_value=target_value,
    )


def _sell_intent(
    symbol,
    rating,
    trade_date,
    delta,
    current_value,
    target_value,
    fractional_shares,
    position,
    skipped,
) -> Optional[OrderIntent]:
    if position is None or position.qty <= 0:
        # No long position to reduce. Shorting is out of scope, so this is a
        # no-op rather than an entry.
        skipped.append(f"{symbol}: {delta:+.2f} would require shorting; skipped")
        return None

    if position.current_price <= 0:
        skipped.append(f"{symbol}: no usable price on the open position; skipped")
        return None

    if target_value <= 0:
        # Full exit: sell the exact share count so no dust is left behind.
        qty = position.qty
    else:
        qty = min(abs(delta) / position.current_price, position.qty)
        if not fractional_shares:
            qty = float(int(qty))
        if qty <= 0:
            skipped.append(
                f"{symbol}: reduction of {abs(delta):.2f} rounds to 0 shares"
            )
            return None

    return OrderIntent(
        symbol=symbol,
        side=SELL,
        client_order_id=client_order_id(symbol, trade_date, rating, SELL),
        reason=f"{rating}: cut exposure {current_value:.2f} -> {target_value:.2f}",
        qty=round(qty, 9),
        rating=rating,
        trade_date=trade_date,
        current_value=current_value,
        target_value=target_value,
    )
