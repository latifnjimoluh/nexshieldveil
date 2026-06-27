"""Configuration schema and loading."""

from __future__ import annotations

from privacy_guard.config.loader import load_config
from privacy_guard.config.models import (
    AppConfig,
    CameraConfig,
    DetectionConfig,
    GeometryConfig,
    MaskingConfig,
    MaskStrategyName,
    PolicyConfig,
    PrimaryUserConfig,
    TrackingConfig,
)

__all__ = [
    "AppConfig",
    "CameraConfig",
    "DetectionConfig",
    "GeometryConfig",
    "MaskStrategyName",
    "MaskingConfig",
    "PolicyConfig",
    "PrimaryUserConfig",
    "TrackingConfig",
    "load_config",
]
