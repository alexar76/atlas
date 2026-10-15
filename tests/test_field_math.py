"""Stdlib field estimators — same numbers as Murmuration's unit tests."""

from __future__ import annotations

import pytest

from atlas.field_math import median, trimmed_mean


def test_median_known_input():
    assert median([3, 1, 2]) == 2.0
    # even count -> average of the two middle values
    assert median([1, 2, 3, 4]) == 2.5


def test_trimmed_mean_drops_tails():
    # 10 values; trim=0.1 drops one from each end -> mean of 2..9
    data = list(range(1, 11))  # 1..10, mean = 5.5
    tm = trimmed_mean(data, trim=0.1)
    assert tm == pytest.approx(sum(range(2, 10)) / 8)
    assert trimmed_mean(data, trim=0.0) == pytest.approx(5.5)
