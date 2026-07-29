"""Refining the gaze estimate with the iris position (AM-9).

Until now the gaze was the *head pose* and nothing else. Six landmarks fed
``solvePnP``, and the answer to "is this person looking at my screen?" was
entirely "where is their head pointing?". Two everyday cases break that:

* someone keeps their head straight and just moves their **eyes** to your screen —
  read as "not looking" (a false negative, i.e. a real leak);
* you turn your head to talk to a colleague while your eyes stay on your own
  screen — read as looking away.

MediaPipe's Face Landmarker already returns iris landmarks; the project simply
never used them. This module turns them into a small angular correction added to
the head pose.

**Deliberately off by default** (``detection.use_iris``). The model below is a
linear approximation of eye rotation, and only a real camera can say whether it
helps or hurts in practice: a wrong iris offset does not just fail to improve
detection, it *moves* the gaze ray and can create false positives where there
were none. Turning it on before that measurement would be exactly the kind of
unverified claim this project refuses elsewhere.

Pure maths, no landmark format, no hardware: the detector adapter extracts the
points, this decides what they mean.
"""

from __future__ import annotations

# A comfortable eye rotation is roughly +-25 degrees before the head follows;
# beyond that people turn their head, which the pose term already captures.
DEFAULT_MAX_OFFSET_DEG = 25.0
# Below this, the eye opening is too small to read a direction from (a blink, a
# profile view, a bad detection). Normalised against the eye's own width.
_MIN_EXTENT = 1e-6


def _normalised_position(value: float, low: float, high: float) -> float | None:
    """Where ``value`` sits in ``[low, high]``, mapped to ``[-1, 1]``.

    ``None`` when the interval is degenerate — a closed or unreadable eye must
    yield "no information", never a confident zero.
    """
    extent = high - low
    if abs(extent) < _MIN_EXTENT:
        return None
    ratio = (value - low) / extent
    return max(-1.0, min(1.0, ratio * 2.0 - 1.0))


def iris_offset_deg(
    iris_x: float,
    iris_y: float,
    inner_x: float,
    outer_x: float,
    top_y: float,
    bottom_y: float,
    max_offset_deg: float = DEFAULT_MAX_OFFSET_DEG,
) -> tuple[float, float]:
    """Angular offset implied by where the iris sits inside the eye opening.

    All coordinates are in the same 2D space (normalised image space works), with
    ``x`` growing right and ``y`` growing **down**, as image coordinates do.

    Args:
        iris_x: Iris centre, horizontal.
        iris_y: Iris centre, vertical.
        inner_x: Eye corner nearest the nose.
        outer_x: Eye corner nearest the ear.
        top_y: Upper eyelid.
        bottom_y: Lower eyelid.
        max_offset_deg: Deflection at a fully deviated iris.

    Returns:
        ``(yaw_offset_deg, pitch_offset_deg)``. Positive yaw deviates toward the
        viewer's right and positive pitch upward, matching
        :func:`~privacy_guard.geometry.gaze.gaze_vector`. A degenerate eye box
        yields ``(0.0, 0.0)`` — no information, so no correction.

    Raises:
        ValueError: If ``max_offset_deg`` is negative.
    """
    if max_offset_deg < 0.0:
        msg = f"max_offset_deg must be >= 0, got {max_offset_deg}"
        raise ValueError(msg)

    # Order the corners so the caller can pass a left or a right eye without
    # worrying which of inner/outer is the larger x.
    low_x, high_x = (inner_x, outer_x) if inner_x <= outer_x else (outer_x, inner_x)
    horizontal = _normalised_position(iris_x, low_x, high_x)
    # Image y grows downward, so a smaller y is *up*: swap the bounds to make a
    # high iris come out as a positive (upward) pitch.
    vertical = _normalised_position(iris_y, bottom_y, top_y)

    yaw = 0.0 if horizontal is None else horizontal * max_offset_deg
    pitch = 0.0 if vertical is None else vertical * max_offset_deg
    return (yaw, pitch)


def compose_gaze(
    head_yaw_deg: float,
    head_pitch_deg: float,
    iris_yaw_deg: float,
    iris_pitch_deg: float,
    weight: float = 1.0,
) -> tuple[float, float]:
    """Add a weighted iris offset to the head pose.

    ``weight = 0`` reproduces the head-pose-only behaviour exactly, which is what
    makes this safe to ship disabled: the composition is the identity until
    someone opts in.

    Raises:
        ValueError: If ``weight`` is outside ``[0, 1]``.
    """
    if not 0.0 <= weight <= 1.0:
        msg = f"weight must be in [0, 1], got {weight}"
        raise ValueError(msg)
    return (
        head_yaw_deg + weight * iris_yaw_deg,
        head_pitch_deg + weight * iris_pitch_deg,
    )
