"""Unit + property tests for tracking filters."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from privacy_guard.tracking import ExponentialSmoother, Kalman1D

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- #
# ExponentialSmoother
# --------------------------------------------------------------------------- #
def test_alpha_out_of_range_rejected() -> None:
    for bad in (0.0, -0.1, 1.1):
        with pytest.raises(ValueError, match="alpha"):
            ExponentialSmoother(bad)


def test_first_update_returns_measurement() -> None:
    s = ExponentialSmoother(0.3)
    assert s.update(5.0) == 5.0
    assert s.value == 5.0


def test_alpha_one_is_passthrough() -> None:
    s = ExponentialSmoother(1.0)
    for v in (1.0, 9.0, -3.0, 4.0):
        assert s.update(v) == v


def test_reset_clears_state() -> None:
    s = ExponentialSmoother(0.5)
    s.update(10.0)
    s.reset()
    assert s.value is None
    assert s.update(2.0) == 2.0


@given(
    target=st.floats(-100, 100, allow_nan=False),
    alpha=st.floats(0.05, 0.95, allow_nan=False),
)
def test_converges_to_constant_input(target: float, alpha: float) -> None:
    s = ExponentialSmoother(alpha)
    out = s.update(target)
    for _ in range(500):
        out = s.update(target)
    assert out == pytest.approx(target, abs=1e-3)


@given(alpha=st.floats(0.05, 0.95, allow_nan=False))
def test_output_stays_within_input_range(alpha: float) -> None:
    s = ExponentialSmoother(alpha)
    data = [1.0, 5.0, 3.0, 9.0, 2.0, 7.0]
    outs = [s.update(x) for x in data]
    assert min(data) <= min(outs)
    assert max(outs) <= max(data)


def test_reduces_noise_variance() -> None:
    rng = np.random.default_rng(42)
    truth = 10.0
    noisy = truth + rng.normal(0, 2.0, size=2000)
    s = ExponentialSmoother(0.1)
    filtered = np.array([s.update(float(x)) for x in noisy])
    # Discard warm-up; smoothing must shrink the variance markedly.
    assert filtered[200:].var() < noisy[200:].var() / 2.0


def test_works_on_vectors() -> None:
    s = ExponentialSmoother(0.5)
    a = np.array([0.0, 0.0, 0.0])
    b = np.array([2.0, 4.0, 6.0])
    s.update(a)
    out = s.update(b)
    assert np.allclose(out, [1.0, 2.0, 3.0])
    # Seeding must not alias the caller's array.
    s2 = ExponentialSmoother(0.5)
    seed = np.array([1.0, 1.0])
    s2.update(seed)
    seed[0] = 999.0
    assert s2.value is not None
    assert not np.allclose(s2.value, [999.0, 1.0])


# --------------------------------------------------------------------------- #
# Kalman1D
# --------------------------------------------------------------------------- #
def test_kalman_rejects_bad_params() -> None:
    with pytest.raises(ValueError, match="positive"):
        Kalman1D(process_var=0.0)
    with pytest.raises(ValueError, match="positive"):
        Kalman1D(measurement_var=-1.0)


def test_kalman_converges_to_constant() -> None:
    k = Kalman1D(process_var=1e-4, measurement_var=0.1, initial_value=0.0)
    out = 0.0
    for _ in range(300):
        out = k.update(20.0)
    assert out == pytest.approx(20.0, abs=0.1)


def test_kalman_reduces_noise_variance() -> None:
    rng = np.random.default_rng(7)
    truth = -5.0
    noisy = truth + rng.normal(0, 3.0, size=2000)
    k = Kalman1D(process_var=1e-4, measurement_var=2.0, initial_value=-5.0)
    filtered = np.array([k.update(float(x)) for x in noisy])
    assert filtered[200:].var() < noisy[200:].var() / 2.0
