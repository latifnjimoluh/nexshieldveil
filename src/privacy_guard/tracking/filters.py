"""Smoothing filters for noisy per-frame estimates (positions, angles).

We deliberately keep these simple and conservative. Webcam-based estimates are
noisy (1.5-3 degrees typical gaze error); smoothing trades a little latency for
far fewer spurious jumps, which in turn reduces masking flicker downstream.
"""

from __future__ import annotations

from typing import TypeVar

import numpy as np
from numpy.typing import NDArray

# EMA/Kalman work identically on a scalar or a numpy vector.
Numeric = TypeVar("Numeric", float, NDArray[np.float64])


class ExponentialSmoother:
    """Exponential moving average (EMA) filter.

    ``output = alpha * measurement + (1 - alpha) * previous_output``.
    ``alpha`` close to 1 is reactive (little smoothing); close to 0 is very smooth.
    """

    def __init__(self, alpha: float) -> None:
        """Initialise the smoother.

        Args:
            alpha: Smoothing factor in ``(0, 1]``.

        Raises:
            ValueError: If ``alpha`` is outside ``(0, 1]``.
        """
        if not 0.0 < alpha <= 1.0:
            msg = f"alpha must be in (0, 1], got {alpha}"
            raise ValueError(msg)
        self.alpha = alpha
        self._state: float | NDArray[np.float64] | None = None

    @property
    def value(self) -> float | NDArray[np.float64] | None:
        """The current filtered value, or ``None`` before the first update."""
        return self._state

    def reset(self) -> None:
        """Forget all history."""
        self._state = None

    def update(self, measurement: Numeric) -> Numeric:
        """Feed a new measurement and return the updated filtered value."""
        if self._state is None:
            # Seed with the first measurement (copy arrays to avoid aliasing).
            self._state = (
                np.array(measurement, dtype=np.float64)
                if isinstance(measurement, np.ndarray)
                else float(measurement)
            )
            return measurement
        self._state = self.alpha * measurement + (1.0 - self.alpha) * self._state
        return self._state  # type: ignore[return-value]


class Kalman1D:
    """Minimal constant-position scalar Kalman filter (e.g. for a single angle).

    A pragmatic 1D filter: the state is a scalar value with a constant-position
    model. ``process_var`` models how quickly the true value may drift;
    ``measurement_var`` models sensor noise. Larger ``measurement_var`` => smoother.

    Provided as a utility for smoothing continuous head-pose **angles**. The default
    pipeline smooths the *binary* observer signal with :class:`ExponentialSmoother`
    instead (a Kalman model is ill-suited to a 0/1 input), so this class is not wired
    into the app today; it is kept for the angle-smoothing path.
    """

    def __init__(
        self,
        process_var: float = 1e-3,
        measurement_var: float = 1e-1,
        initial_value: float = 0.0,
        initial_uncertainty: float = 1.0,
    ) -> None:
        """Initialise the filter.

        Raises:
            ValueError: If any variance/uncertainty is non-positive.
        """
        if process_var <= 0 or measurement_var <= 0 or initial_uncertainty <= 0:
            msg = "variances and uncertainty must be positive"
            raise ValueError(msg)
        self.process_var = process_var
        self.measurement_var = measurement_var
        self._x = initial_value
        self._p = initial_uncertainty

    @property
    def value(self) -> float:
        """The current state estimate."""
        return self._x

    def update(self, measurement: float) -> float:
        """Run one predict+update step and return the new estimate."""
        # Predict: constant-position model, uncertainty grows by process noise.
        p_pred = self._p + self.process_var
        # Update: blend prediction with measurement by the Kalman gain.
        gain = p_pred / (p_pred + self.measurement_var)
        self._x = self._x + gain * (measurement - self._x)
        self._p = (1.0 - gain) * p_pred
        return self._x
