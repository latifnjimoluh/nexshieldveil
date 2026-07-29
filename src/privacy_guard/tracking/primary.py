"""Temporal hysteresis on *who* the primary user is (AM-8).

:func:`~privacy_guard.geometry.gaze.select_primary_user` scores faces frame by
frame with no memory. That is a problem in the product's main use case — two
people sitting side by side at comparable distance — because their scores are
close, a micro-movement flips the title, and the title decides **whose gaze is
ignored**. Every flip inverts the decision: the real user is suddenly treated as
an observer (false positive) and the observer as the user (false negative).

Neither existing layer fixes this. The EMA in :mod:`~privacy_guard.tracking.filters`
smooths the *final boolean*, and the hysteresis in :mod:`~privacy_guard.policy`
delays a state change — but an identity inversion feeds them both a signal that is
already wrong, so they only slow the oscillation down.

:class:`PrimaryUserSelector` adds the missing memory:

* the incumbent keeps the title unless a challenger beats it by ``margin``
  **for ``patience`` consecutive frames**;
* the incumbent is followed across frames by *position*, not by list index —
  detector output is an unordered list, so index 0 is not the same face twice.

Still no identity, ever: matching is nearest-centroid in normalised image space,
the same geometry the scoring already uses. Nothing is stored beyond one
frame's worth of coordinates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from privacy_guard.geometry.types import FaceCandidate


@dataclass(frozen=True)
class _Tracked:
    """The last known position/size of a face we are following."""

    center_x: float
    center_y: float
    size: float

    @classmethod
    def of(cls, face: FaceCandidate) -> _Tracked:
        """Snapshot a candidate's geometry."""
        return cls(face.center_x, face.center_y, face.size)

    def distance_to(self, face: FaceCandidate) -> float:
        """Euclidean distance in normalised image space."""
        return math.hypot(self.center_x - face.center_x, self.center_y - face.center_y)


class PrimaryUserSelector:
    """Picks the primary user with hysteresis, so the title stops oscillating.

    Args:
        centrality_weight: Weight for centrality in the score.
        size_weight: Weight for relative face size in the score.
        margin: How much better a challenger must score than the incumbent to
            start counting toward a switch. ``0`` makes any lead count.
        patience: Consecutive frames the challenger must keep that lead.
            ``1`` restores the memoryless behaviour.
        match_distance: Maximum normalised distance at which a face is
            considered to be the same one as last frame. Beyond it, the
            incumbent is treated as gone.

    Raises:
        ValueError: If ``margin``/``match_distance`` are negative or
            ``patience`` is below 1.
    """

    def __init__(
        self,
        centrality_weight: float = 1.0,
        size_weight: float = 1.0,
        margin: float = 0.08,
        patience: int = 3,
        match_distance: float = 0.15,
    ) -> None:
        """Initialise the selector with no incumbent."""
        if margin < 0.0:
            msg = f"margin must be >= 0, got {margin}"
            raise ValueError(msg)
        if patience < 1:
            msg = f"patience must be >= 1, got {patience}"
            raise ValueError(msg)
        if match_distance < 0.0:
            msg = f"match_distance must be >= 0, got {match_distance}"
            raise ValueError(msg)
        self.centrality_weight = centrality_weight
        self.size_weight = size_weight
        self.margin = margin
        self.patience = patience
        self.match_distance = match_distance
        self._incumbent: _Tracked | None = None
        self._challenger: _Tracked | None = None
        self._streak = 0

    @property
    def has_incumbent(self) -> bool:
        """Whether a primary user is currently held over from earlier frames."""
        return self._incumbent is not None

    @property
    def challenger_streak(self) -> int:
        """Consecutive frames the current challenger has been ahead (diagnostics)."""
        return self._streak

    def reset(self) -> None:
        """Forget the incumbent and any challenge in progress."""
        self._incumbent = None
        self._challenger = None
        self._streak = 0

    def update(self, faces: list[FaceCandidate]) -> int | None:
        """Return the index of the primary user in ``faces``, or ``None`` if empty.

        Call once per frame, in order: the result depends on the previous calls.
        """
        from privacy_guard.geometry.gaze import primary_user_scores

        if not faces:
            # Everyone left the frame: nothing to hold on to.
            self.reset()
            return None

        scores = primary_user_scores(faces, self.centrality_weight, self.size_weight)
        best = max(range(len(faces)), key=lambda i: scores[i])

        incumbent_idx = self._match(faces)
        if incumbent_idx is None:
            # First frame, or the incumbent is gone: take the best on the spot.
            self._elect(faces[best])
            return best

        # Refresh the incumbent's tracked position (it moves between frames).
        self._incumbent = _Tracked.of(faces[incumbent_idx])

        if best == incumbent_idx or scores[best] < scores[incumbent_idx] + self.margin:
            # No challenge, or not a big enough lead to count: the title stands.
            self._challenger = None
            self._streak = 0
            return incumbent_idx

        challenger = faces[best]
        if self._challenger is not None and self._is_same(self._challenger, challenger):
            self._streak += 1
        else:
            # A different face took the lead: its streak starts now.
            self._streak = 1
        self._challenger = _Tracked.of(challenger)

        if self._streak >= self.patience:
            self._elect(challenger)
            return best
        return incumbent_idx

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    def _elect(self, face: FaceCandidate) -> None:
        self._incumbent = _Tracked.of(face)
        self._challenger = None
        self._streak = 0

    def _match(self, faces: list[FaceCandidate]) -> int | None:
        """Index of the face closest to the incumbent, within ``match_distance``."""
        if self._incumbent is None:
            return None
        distances = [self._incumbent.distance_to(face) for face in faces]
        closest = min(range(len(faces)), key=lambda i: distances[i])
        return closest if distances[closest] <= self.match_distance else None

    def _is_same(self, tracked: _Tracked, face: FaceCandidate) -> bool:
        return tracked.distance_to(face) <= self.match_distance
