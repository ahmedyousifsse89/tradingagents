"""Tests for the rating -> target weight policy."""

from __future__ import annotations

import pytest

from tradingagents.agents.utils.rating import RATINGS_5_TIER
from tradingagents.execution.sizing import DEFAULT_TARGET_WEIGHTS, TargetWeightPolicy


def test_default_weights_cover_every_rating():
    assert set(DEFAULT_TARGET_WEIGHTS) == set(RATINGS_5_TIER)


@pytest.mark.parametrize(
    "rating,expected",
    [("Buy", 0.08), ("Overweight", 0.04), ("Underweight", 0.02), ("Sell", 0.0)],
)
def test_explicit_ratings_map_to_configured_weights(rating, expected):
    policy = TargetWeightPolicy()
    assert policy.target_weight(rating, current_weight=0.05) == expected


def test_hold_keeps_the_current_weight():
    policy = TargetWeightPolicy()
    assert policy.target_weight("Hold", current_weight=0.037) == 0.037
    assert policy.target_weight("Hold", current_weight=0.0) == 0.0


def test_unknown_rating_is_treated_as_hold():
    policy = TargetWeightPolicy()
    assert policy.target_weight("Strong Buy", current_weight=0.03) == 0.03


def test_per_position_cap_applies_to_explicit_ratings():
    policy = TargetWeightPolicy(weights={"Buy": 0.50}, max_position_weight=0.10)
    assert policy.target_weight("Buy", current_weight=0.0) == 0.10


def test_per_position_cap_trims_an_oversized_hold():
    # An inherited position above the cap should get cut back, not
    # grandfathered in just because the rating says Hold.
    policy = TargetWeightPolicy(max_position_weight=0.10)
    assert policy.target_weight("Hold", current_weight=0.25) == 0.10


def test_missing_rating_is_rejected():
    # Custom weights are merged onto the defaults, so a gap can only appear
    # if the table is mutated after construction. Validation must still catch it.
    policy = TargetWeightPolicy()
    del policy.weights["Overweight"]
    with pytest.raises(ValueError, match="no target weight configured"):
        policy._validate()


def test_negative_weight_is_rejected():
    with pytest.raises(ValueError, match="shorting is not supported"):
        TargetWeightPolicy(weights={"Sell": -0.05})


def test_non_positive_max_position_weight_is_rejected():
    with pytest.raises(ValueError, match="max_position_weight must be > 0"):
        TargetWeightPolicy(max_position_weight=0.0)
