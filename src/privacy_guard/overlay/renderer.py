"""Renderer interface for the masking layer, plus a headless recording renderer.

The pipeline only talks to the :class:`Renderer` interface, so it can be driven and
asserted in tests via :class:`RecordingRenderer` without ever opening a real window.
This is also the observable hook used by system/E2E tests.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Renderer(ABC):
    """Controls whether the on-screen masking layer is engaged."""

    @abstractmethod
    def set_masked(self, masked: bool) -> None:
        """Engage (``True``) or lift (``False``) the masking layer."""

    @property
    @abstractmethod
    def is_masked(self) -> bool:
        """Whether the masking layer is currently engaged."""

    def close(self) -> None:  # noqa: B027 - optional override; default no-op is intentional
        """Release any resources (no-op by default)."""


class RecordingRenderer(Renderer):
    """A headless renderer that records masking transitions.

    Useful as a test double and as an observable hook for E2E assertions: it tracks
    the current state, every state *transition*, and the total number of calls.
    """

    def __init__(self) -> None:
        """Initialise in the unmasked state with empty history."""
        self._masked = False
        self.transitions: list[bool] = []
        self.calls = 0

    def set_masked(self, masked: bool) -> None:
        """Set the masked state, recording only genuine transitions."""
        self.calls += 1
        if masked != self._masked:
            self._masked = masked
            self.transitions.append(masked)

    @property
    def is_masked(self) -> bool:
        """Current masked state."""
        return self._masked

    @property
    def mask_engaged_count(self) -> int:
        """How many times the mask transitioned to engaged."""
        return sum(1 for t in self.transitions if t)
