"""Unit tests for resource resolution (source vs frozen)."""

from __future__ import annotations

from pathlib import Path

import pytest

from privacy_guard import resources

pytestmark = pytest.mark.unit


def test_not_frozen_by_default() -> None:
    assert resources.is_frozen() is False


def test_default_model_path_ends_with_relative() -> None:
    p = Path(resources.default_model_path())
    assert p.name == "face_landmarker.task"
    assert p.parent.name == "models"


def test_resource_root_uses_meipass_when_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resources.sys, "_MEIPASS", r"C:\bundle", raising=False)
    root = resources.resource_root()
    assert str(root) == r"C:\bundle"
    assert resources.default_model_path().startswith(r"C:\bundle")
