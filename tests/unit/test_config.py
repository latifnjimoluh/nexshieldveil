"""Unit tests for the config module (schema defaults, TOML loading, validation)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from privacy_guard.config import AppConfig, load_config

pytestmark = pytest.mark.unit


def test_default_config_is_valid() -> None:
    cfg = AppConfig()
    # Conservative anti-flicker defaults: release must be >= trigger.
    assert cfg.policy.trigger_ms > 0
    assert cfg.policy.release_ms >= cfg.policy.trigger_ms
    assert 0.0 < cfg.tracking.smoothing_alpha <= 1.0
    assert 0.0 < cfg.geometry.gaze_tolerance_deg < 90.0


def test_load_minimal_toml_uses_defaults(tmp_path: Path) -> None:
    toml = tmp_path / "config.toml"
    toml.write_text("[policy]\ntrigger_ms = 250\n", encoding="utf-8")
    cfg = load_config(toml)
    assert cfg.policy.trigger_ms == 250
    # Untouched sections keep their defaults.
    assert cfg.tracking.smoothing_alpha == AppConfig().tracking.smoothing_alpha


def test_load_full_toml_overrides(tmp_path: Path) -> None:
    toml = tmp_path / "config.toml"
    toml.write_text(
        "\n".join(
            [
                "[camera]",
                "device_index = 1",
                "enabled = false",
                "[policy]",
                "trigger_ms = 300",
                "release_ms = 900",
                "[geometry]",
                "gaze_tolerance_deg = 12.5",
                "[masking]",
                'strategy = "pixelate"',
            ]
        ),
        encoding="utf-8",
    )
    cfg = load_config(toml)
    assert cfg.camera.device_index == 1
    assert cfg.camera.enabled is False
    assert cfg.policy.release_ms == 900
    assert cfg.geometry.gaze_tolerance_deg == 12.5
    assert cfg.masking.strategy == "pixelate"


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "does-not-exist.toml")


def test_release_must_not_be_below_trigger(tmp_path: Path) -> None:
    toml = tmp_path / "config.toml"
    toml.write_text("[policy]\ntrigger_ms = 800\nrelease_ms = 100\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_config(toml)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("tracking", "smoothing_alpha", 0.0),
        ("tracking", "smoothing_alpha", 1.5),
        ("geometry", "gaze_tolerance_deg", 0.0),
        ("geometry", "gaze_tolerance_deg", 95.0),
        ("policy", "trigger_ms", -10),
        ("camera", "target_fps", 0),
    ],
)
def test_out_of_bounds_values_rejected(section: str, field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        AppConfig(**{section: {field: value}})


def test_invalid_masking_strategy_rejected() -> None:
    with pytest.raises(ValidationError):
        AppConfig(masking={"strategy": "teleport"})


def test_unknown_keys_rejected(tmp_path: Path) -> None:
    toml = tmp_path / "config.toml"
    toml.write_text("[policy]\nnot_a_real_field = 1\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_config(toml)


def test_round_trips_through_dict() -> None:
    cfg = AppConfig()
    again = AppConfig(**cfg.model_dump())
    assert again == cfg
