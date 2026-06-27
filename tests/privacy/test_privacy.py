"""Privacy guarantees (crucial): no network, no frame persistence, no buffer growth.

These encode the project's non-negotiable privacy-by-design rules. They must fail
loudly if any future change opens a socket, writes an image to disk, or starts
accumulating frame buffers across iterations.
"""

from __future__ import annotations

import builtins
import gc
import socket
import weakref

import numpy as np
import pytest

from privacy_guard.app import PrivacyGuardPipeline
from privacy_guard.capture import Frame, SyntheticFrameSource
from privacy_guard.config import AppConfig
from privacy_guard.overlay import RecordingRenderer
from privacy_guard.vision import ScriptedFaceDetector
from tests.conftest import FPS, session_script

pytestmark = pytest.mark.privacy


def _run_session() -> None:
    script = session_script()
    pipeline = PrivacyGuardPipeline(
        AppConfig(),
        SyntheticFrameSource(n_frames=len(script), fps=FPS),
        ScriptedFaceDetector(script),
        RecordingRenderer(),
    )
    pipeline.run()
    pipeline.close()


def test_no_outbound_network_during_run(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[str] = []

    def forbid(*args: object, **kwargs: object) -> object:
        attempts.append("network call")
        raise AssertionError("outbound network attempted")

    monkeypatch.setattr(socket, "socket", forbid)
    monkeypatch.setattr(socket, "create_connection", forbid)
    monkeypatch.setattr(socket, "getaddrinfo", forbid)

    _run_session()
    assert attempts == []


def test_no_files_written_during_run(monkeypatch: pytest.MonkeyPatch) -> None:
    real_open = builtins.open
    writes: list[tuple[str, str]] = []

    def spy_open(file: object, mode: str = "r", *args: object, **kwargs: object) -> object:
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            writes.append((str(file), mode))
        return real_open(file, mode, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "open", spy_open)

    # Also forbid the common image/array persistence calls.
    def forbid_save(*args: object, **kwargs: object) -> None:
        raise AssertionError("array/image persistence attempted")

    monkeypatch.setattr(np, "save", forbid_save)
    monkeypatch.setattr(np, "savez", forbid_save)

    _run_session()
    assert writes == [], f"unexpected file writes during run: {writes}"


def test_no_image_files_appear_on_disk(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Run inside an empty CWD and assert no image artifacts are left behind.
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.rglob("*"))
    _run_session()
    after = set(tmp_path.rglob("*"))
    new_files = after - before
    image_exts = {".png", ".jpg", ".jpeg", ".bmp", ".npy", ".npz", ".tiff"}
    assert not [p for p in new_files if p.suffix.lower() in image_exts]


def test_frames_are_not_accumulated(monkeypatch: pytest.MonkeyPatch) -> None:
    refs: list[weakref.ref[Frame]] = []

    class TrackingSource(SyntheticFrameSource):
        def read(self) -> Frame | None:
            frame = super().read()
            if frame is not None:
                refs.append(weakref.ref(frame))
            return frame

    pipeline = PrivacyGuardPipeline(
        AppConfig(),
        TrackingSource(n_frames=60, fps=FPS),
        ScriptedFaceDetector([]),
        RecordingRenderer(),
    )
    pipeline.run()

    gc.collect()
    alive = sum(1 for ref in refs if ref() is not None)
    # No frame may survive past its iteration (allow the single most-recent one).
    assert alive <= 1, f"{alive} frames still alive — buffers are being accumulated"


def test_pipeline_retains_no_image_data() -> None:
    script = session_script()
    pipeline = PrivacyGuardPipeline(
        AppConfig(),
        SyntheticFrameSource(n_frames=len(script), fps=FPS),
        ScriptedFaceDetector(script),
        RecordingRenderer(),
    )
    pipeline.run()
    # The only retained per-frame artifact is FrameResult (scalars), never an image.
    assert pipeline.last_result is not None
    for value in vars(pipeline.last_result).values():
        assert not isinstance(value, np.ndarray)
