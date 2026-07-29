"""Primary-user election hysteresis (AM-8): the title must stop oscillating.

Pure logic — no camera. The scenario that matters is two people side by side at
comparable distance: their scores are close, so a memoryless election flips the
title on a micro-movement, and the title decides whose gaze is ignored.
"""

from __future__ import annotations

import pytest

from privacy_guard.geometry import FaceCandidate, primary_user_scores, select_primary_user
from privacy_guard.tracking import PrimaryUserSelector

pytestmark = pytest.mark.unit


def _face(x: float, y: float = 0.5, size: float = 0.2) -> FaceCandidate:
    return FaceCandidate(center_x=x, center_y=y, size=size)


# --------------------------------------------------------------------------- #
# the score function the election is built on
# --------------------------------------------------------------------------- #
def test_scores_rank_the_central_face_first() -> None:
    scores = primary_user_scores([_face(0.5), _face(0.1)])
    assert scores[0] > scores[1]


def test_scores_reward_a_bigger_face() -> None:
    scores = primary_user_scores([_face(0.5, size=0.4), _face(0.5, size=0.1)])
    assert scores[0] > scores[1]


def test_scores_agree_with_the_single_frame_winner() -> None:
    faces = [_face(0.2), _face(0.5), _face(0.9)]
    scores = primary_user_scores(faces)
    assert scores.index(max(scores)) == select_primary_user(faces)


def test_scores_are_empty_for_no_faces() -> None:
    assert primary_user_scores([]) == []


# --------------------------------------------------------------------------- #
# constructor validation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "kwargs",
    [{"margin": -0.1}, {"patience": 0}, {"patience": -2}, {"match_distance": -0.01}],
)
def test_invalid_parameters_are_rejected(kwargs) -> None:
    with pytest.raises(ValueError):
        PrimaryUserSelector(**kwargs)


# --------------------------------------------------------------------------- #
# basic election
# --------------------------------------------------------------------------- #
def test_no_faces_yields_no_primary() -> None:
    assert PrimaryUserSelector().update([]) is None


def test_the_first_frame_elects_the_best_scoring_face() -> None:
    selector = PrimaryUserSelector()
    assert selector.update([_face(0.1), _face(0.5)]) == 1
    assert selector.has_incumbent is True


def test_a_lone_face_is_the_primary_user() -> None:
    assert PrimaryUserSelector().update([_face(0.05, size=0.05)]) == 0


# --------------------------------------------------------------------------- #
# the point of the whole module: no flip-flopping
# --------------------------------------------------------------------------- #
def test_a_marginal_lead_never_takes_the_title() -> None:
    # Two people side by side, the challenger microscopically better every frame.
    selector = PrimaryUserSelector(margin=0.08, patience=3)
    assert selector.update([_face(0.45), _face(0.55)]) == 0  # 0.45 is nearer centre
    for _ in range(20):
        assert selector.update([_face(0.45), _face(0.549)]) == 0
    assert selector.challenger_streak == 0  # the lead never even counted


def test_a_clear_and_sustained_lead_does_take_the_title() -> None:
    selector = PrimaryUserSelector(margin=0.05, patience=3)
    assert selector.update([_face(0.5, size=0.2), _face(0.5, size=0.2)]) == 0
    # Face 1 comes much closer to the camera and stays there.
    frames = [[_face(0.5, size=0.2), _face(0.5, size=0.6)] for _ in range(3)]
    results = [selector.update(faces) for faces in frames]
    assert results[:2] == [0, 0]  # patience not yet exhausted
    assert results[2] == 1  # third consecutive frame: the title moves


def test_an_interrupted_challenge_restarts_from_zero() -> None:
    # A challenger that leads, drops back, then leads again must serve the full
    # patience again — otherwise a flickering lead accumulates into a switch.
    selector = PrimaryUserSelector(margin=0.05, patience=3)
    selector.update([_face(0.5, size=0.2), _face(0.5, size=0.2)])
    selector.update([_face(0.5, size=0.2), _face(0.5, size=0.6)])
    selector.update([_face(0.5, size=0.2), _face(0.5, size=0.6)])
    assert selector.update([_face(0.5, size=0.2), _face(0.5, size=0.2)]) == 0  # lead lost
    assert selector.challenger_streak == 0
    assert selector.update([_face(0.5, size=0.2), _face(0.5, size=0.6)]) == 0  # starts over


def test_patience_of_one_restores_memoryless_behaviour() -> None:
    selector = PrimaryUserSelector(margin=0.0, patience=1)
    selector.update([_face(0.5, size=0.2), _face(0.5, size=0.2)])
    assert selector.update([_face(0.5, size=0.2), _face(0.5, size=0.6)]) == 1


# --------------------------------------------------------------------------- #
# following the incumbent by position, not by list index
# --------------------------------------------------------------------------- #
def test_the_incumbent_is_followed_when_the_detector_reorders_faces() -> None:
    # Detector output is an unordered list: index 0 is not the same face twice.
    selector = PrimaryUserSelector()
    assert selector.update([_face(0.5, size=0.4), _face(0.1, size=0.1)]) == 0
    # Same two people, emitted in the opposite order.
    assert selector.update([_face(0.1, size=0.1), _face(0.5, size=0.4)]) == 1


def test_the_incumbent_is_followed_as_it_moves() -> None:
    selector = PrimaryUserSelector(margin=0.5, patience=99)  # never switch on score
    selector.update([_face(0.50), _face(0.9)])
    for x in (0.52, 0.54, 0.56, 0.58):
        assert selector.update([_face(x), _face(0.9)]) == 0


def test_a_departed_incumbent_hands_the_title_over_at_once() -> None:
    # No point holding a title for someone who left the frame.
    selector = PrimaryUserSelector(margin=0.5, patience=99)
    selector.update([_face(0.5, size=0.4), _face(0.9, size=0.1)])
    assert selector.update([_face(0.9, size=0.1)]) == 0
    assert selector.has_incumbent is True


def test_an_empty_frame_clears_the_incumbent() -> None:
    selector = PrimaryUserSelector()
    selector.update([_face(0.5)])
    assert selector.update([]) is None
    assert selector.has_incumbent is False


def test_a_teleporting_face_is_not_matched_to_the_incumbent() -> None:
    # Beyond match_distance it is a different face, so the election restarts
    # rather than silently transferring the title across the frame.
    selector = PrimaryUserSelector(match_distance=0.1, margin=0.5, patience=99)
    selector.update([_face(0.2, size=0.5)])
    assert selector.update([_face(0.9, size=0.5)]) == 0
    assert selector.has_incumbent is True


def test_reset_forgets_everything() -> None:
    selector = PrimaryUserSelector()
    selector.update([_face(0.5)])
    selector.reset()
    assert selector.has_incumbent is False
    assert selector.challenger_streak == 0


# --------------------------------------------------------------------------- #
# the property that matters end to end
# --------------------------------------------------------------------------- #
def test_noise_around_a_tie_produces_no_switch_at_all() -> None:
    # Two people side by side, equidistant, breathing/leaning by a couple of
    # millimetres — so the tiny size difference changes sign every frame. This
    # is the real-world case a memoryless election handles worst.
    def frame(delta: float) -> list[FaceCandidate]:
        return [_face(0.45, size=0.20 + delta), _face(0.55, size=0.20 - delta)]

    jitter = [0.002, -0.002, 0.001, -0.001, 0.003, -0.003] * 6
    selector = PrimaryUserSelector(margin=0.05, patience=3)
    first = selector.update(frame(0.0))
    results = [selector.update(frame(d)) for d in jitter]
    assert set(results) == {first}, "the primary user must not change on noise"

    # Anti-tautology: the same jitter DOES flip a memoryless election.
    naive = [select_primary_user(frame(d)) for d in jitter]
    assert len(set(naive)) == 2, "this jitter is supposed to flip the naive election"
