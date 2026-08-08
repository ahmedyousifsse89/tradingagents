"""Rating to target-weight mapping.

Position size is decided here, deterministically, and never by an LLM. The
Trader agent's ``position_sizing`` field is free-form prose (see
:class:`tradingagents.agents.schemas.TraderProposal`) and is deliberately not
parsed into share counts — a model that writes "a starter position, maybe
scale in later" must not be able to move money.

The only input taken from the pipeline is the 5-tier rating, which comes out
of :func:`tradingagents.agents.utils.rating.parse_rating` and is therefore
always one of the five known strings.
"""

from __future__ import annotations

from typing import Dict, Optional

from tradingagents.agents.utils.rating import RATINGS_5_TIER


# Target fraction of account equity per rating. ``None`` means "leave the
# position where it is" — a Hold is not an instruction to resize to some
# neutral weight, it is an instruction to do nothing.
DEFAULT_TARGET_WEIGHTS: Dict[str, Optional[float]] = {
    "Buy": 0.08,
    "Overweight": 0.04,
    "Hold": None,
    "Underweight": 0.02,
    "Sell": 0.0,
}


class TargetWeightPolicy:
    """Map a 5-tier rating to a target fraction of equity."""

    def __init__(
        self,
        weights: Optional[Dict[str, Optional[float]]] = None,
        max_position_weight: float = 0.10,
    ):
        self.weights = dict(DEFAULT_TARGET_WEIGHTS)
        if weights:
            self.weights.update(weights)
        self.max_position_weight = max_position_weight
        self._validate()

    def _validate(self) -> None:
        for rating in RATINGS_5_TIER:
            if rating not in self.weights:
                raise ValueError(f"no target weight configured for rating {rating!r}")
        for rating, weight in self.weights.items():
            if weight is None:
                continue
            if weight < 0:
                raise ValueError(
                    f"target weight for {rating!r} must be >= 0 (shorting is not "
                    f"supported), got {weight}"
                )
        if self.max_position_weight <= 0:
            raise ValueError(
                f"max_position_weight must be > 0, got {self.max_position_weight}"
            )

    def target_weight(self, rating: str, current_weight: float) -> float:
        """Target weight for ``rating``, given the position's ``current_weight``.

        An unrecognised rating is treated as Hold rather than raising: the
        rating parser already defaults to Hold, and the safe response to an
        unexpected value in the execution path is to leave the book alone.
        """
        weight = self.weights.get(rating, None)
        if weight is None:
            # Hold (or unknown): keep whatever is already on, but still
            # enforce the per-position cap so an inherited oversized
            # position gets trimmed rather than grandfathered in.
            weight = current_weight
        return min(weight, self.max_position_weight)
