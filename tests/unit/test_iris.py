"""Iris-refined gaze (AM-9): the maths, not the landmarks.

Everything here is pure. The MediaPipe side only extracts points; what those
points *mean* is decided by this module, so this is where the behaviour lives —
including the cases where the honest answer is "no information".
"""

from __future__ import annotations

import pytest

from privacy_guard.geometry import compose_gaze, iris_offset_deg

pytestmark = pytest.mark.unit

# A plausible eye in normalised image space: 6 cm wide on screen, y grows DOWN.
_INNER_X, _OUTER_X = 0.40, 0.46
_TOP_Y, _BOTTOM_Y = 0.30, 0.34
_CENTRE_X = (_INNER_X + _OUTER_X) / 2
_CENTRE_Y = (_TOP_Y + _BOTTOM_Y) / 2


def _offset(x: float, y: float, **kwargs) -> tuple[float, float]:
    return iris_offset_deg(x, y, _INNER_X, _OUTER_X, _TOP_Y, _BOTTOM_Y, **kwargs)


# --------------------------------------------------------------------------- #
# the offset itself
# --------------------------------------------------------------------------- #
def test_a_centred_iris_adds_nothing() -> None:
    yaw, pitch = _offset(_CENTRE_X, _CENTRE_Y)
    assert yaw == pytest.approx(0.0, abs=1e-9)
    assert pitch == pytest.approx(0.0, abs=1e-9)


def test_a_fully_deviated_iris_reaches_the_configured_maximum() -> None:
    assert _offset(_OUTER_X, _CENTRE_Y)[0] == pytest.approx(25.0)
    assert _offset(_INNER_X, _CENTRE_Y)[0] == pytest.approx(-25.0)


def test_the_sign_convention_matches_gaze_vector() -> None:
    # Positive yaw is toward the viewer's right (+x), positive pitch is up —
    # and image y grows DOWNWARD, so a small y must give a positive pitch.
    assert _offset(_CENTRE_X, _TOP_Y)[1] > 0
    assert _offset(_CENTRE_X, _BOTTOM_Y)[1] < 0


def test_the_offset_is_proportional_in_between() -> None:
    quarter = _INNER_X + (_OUTER_X - _INNER_X) * 0.75
    assert _offset(quarter, _CENTRE_Y)[0] == pytest.approx(12.5)


def test_an_iris_outside_the_eye_box_is_clamped() -> None:
    # A bad landmark must not produce a 90-degree gaze swing.
    assert _offset(_OUTER_X + 0.5, _CENTRE_Y)[0] == pytest.approx(25.0)
    assert _offset(_INNER_X - 0.5, _CENTRE_Y)[0] == pytest.approx(-25.0)


def test_the_eye_corners_can_be_given_in_either_order() -> None:
    # Left and right eyes have inner/outer on opposite sides; the caller should
    # not have to care.
    swapped = iris_offset_deg(_OUTER_X, _CENTRE_Y, _OUTER_X, _INNER_X, _TOP_Y, _BOTTOM_Y)
    assert swapped[0] == pytest.approx(25.0)


def test_a_closed_eye_yields_no_correction() -> None:
    # A blink collapses the eyelids: no information, so no correction — rather
    # than a confident "looking straight ahead".
    _, pitch = iris_offset_deg(_CENTRE_X, _CENTRE_Y, _INNER_X, _OUTER_X, 0.32, 0.32)
    assert pitch == 0.0


def test_a_degenerate_eye_width_yields_no_correction() -> None:
    yaw, _ = iris_offset_deg(_CENTRE_X, _CENTRE_Y, 0.43, 0.43, _TOP_Y, _BOTTOM_Y)
    assert yaw == 0.0


def test_the_maximum_is_configurable() -> None:
    assert _offset(_OUTER_X, _CENTRE_Y, max_offset_deg=10.0)[0] == pytest.approx(10.0)
    assert _offset(_OUTER_X, _CENTRE_Y, max_offset_deg=0.0)[0] == 0.0


def test_a_negative_maximum_is_rejected() -> None:
    with pytest.raises(ValueError):
        _offset(_CENTRE_X, _CENTRE_Y, max_offset_deg=-1.0)


# --------------------------------------------------------------------------- #
# composition with the head pose
# --------------------------------------------------------------------------- #
def test_a_zero_weight_reproduces_the_head_pose_exactly() -> None:
    # This is what makes the feature safe to ship disabled: off means identity,
    # not "nearly identity".
    assert compose_gaze(12.0, -3.0, 25.0, 25.0, weight=0.0) == (12.0, -3.0)


def test_a_full_weight_adds_the_whole_offset() -> None:
    assert compose_gaze(10.0, 5.0, -4.0, 2.0, weight=1.0) == (6.0, 7.0)


def test_a_partial_weight_scales_the_offset() -> None:
    yaw, pitch = compose_gaze(10.0, 0.0, 20.0, -10.0, weight=0.5)
    assert yaw == pytest.approx(20.0)
    assert pitch == pytest.approx(-5.0)


@pytest.mark.parametrize("weight", [-0.1, 1.1])
def test_an_out_of_range_weight_is_rejected(weight: float) -> None:
    with pytest.raises(ValueError):
        compose_gaze(0.0, 0.0, 0.0, 0.0, weight=weight)


def test_the_feature_is_off_by_default_in_the_config() -> None:
    # The honest default: unvalidated on hardware, so nobody gets it silently.
    from privacy_guard.config import DetectionConfig

    assert DetectionConfig().use_iris is False


def test_the_eyes_looking_sideways_case_the_feature_exists_for() -> None:
    # Head straight at the camera, eyes turned to the screen on the right: the
    # head-pose-only estimate says 0 degrees, which reads as "not looking".
    head_yaw = 0.0
    yaw, _ = compose_gaze(head_yaw, 0.0, *_offset(_OUTER_X, _CENTRE_Y))
    assert head_yaw == 0.0
    assert yaw == pytest.approx(25.0)
