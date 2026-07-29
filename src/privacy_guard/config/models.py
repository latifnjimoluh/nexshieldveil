"""Configuration schema for Privacy Guard.

All thresholds and heuristics are intentionally *configurable* and conservative by
default. We do not claim sub-degree gaze accuracy (webcam gaze typically has
1.5-3 degrees of error), so the default gaze tolerance is generous.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

MaskStrategyName = Literal["veil", "pixelate", "blur"]


class _StrictModel(BaseModel):
    """Base model: reject unknown keys and validate on assignment."""

    model_config = {"extra": "forbid", "validate_assignment": True, "frozen": False}


class CameraConfig(_StrictModel):
    """Webcam capture settings (adapter level)."""

    enabled: bool = True
    device_index: int = Field(default=0, ge=0)
    target_fps: int = Field(default=15, ge=1, le=120)
    downscale_width: int = Field(
        default=640,
        ge=64,
        le=3840,
        description="Frames are downscaled to this width before vision.",
    )
    idle_fps: int = Field(
        default=5,
        ge=1,
        le=120,
        description="Reduced rate used once nobody has been in front of the camera for a while.",
    )
    idle_after_ms: int = Field(
        default=30_000,
        ge=0,
        description="Empty-frame duration before backing off to idle_fps. 0 keeps the full rate.",
    )


class DetectionConfig(_StrictModel):
    """Face/landmark detection settings (MediaPipe wrapper)."""

    model_path: str | None = Field(
        default=None,
        description="Local path to the MediaPipe FaceLandmarker .task model. None = degraded mode.",
    )
    max_faces: int = Field(default=4, ge=1, le=10)
    min_detection_confidence: float = Field(default=0.5, gt=0.0, le=1.0)


class GeometryConfig(_StrictModel):
    """Screen geometry and gaze decision thresholds (pure-logic level)."""

    gaze_tolerance_deg: float = Field(
        default=18.0,
        gt=0.0,
        lt=90.0,
        description="Angular tolerance for 'gaze points at screen'. Generous by default.",
    )
    screen_width_mm: float = Field(default=520.0, gt=0.0)
    screen_height_mm: float = Field(default=290.0, gt=0.0)
    camera_above_screen_mm: float = Field(
        default=10.0, description="Vertical offset of the camera above the screen top edge."
    )


class TrackingConfig(_StrictModel):
    """Smoothing filter settings."""

    smoothing_alpha: float = Field(
        default=0.4,
        gt=0.0,
        le=1.0,
        description="EMA factor: higher = more reactive, lower = smoother.",
    )


class PolicyConfig(_StrictModel):
    """Decision state-machine timings (hysteresis / anti-flicker)."""

    trigger_ms: int = Field(
        default=400, ge=0, description="Sustained observer gaze before masking engages."
    )
    release_ms: int = Field(
        default=800, ge=0, description="Sustained absence before masking lifts (>= trigger_ms)."
    )
    absence_ms: int = Field(
        default=0,
        ge=0,
        le=600_000,
        description=(
            "Walk-away lock: mask after this long with NO face in front of the camera. "
            "0 disables it (default): it changes when the screen hides, so it is opt-in."
        ),
    )

    @model_validator(mode="after")
    def _release_ge_trigger(self) -> PolicyConfig:
        if self.release_ms < self.trigger_ms:
            msg = "release_ms must be >= trigger_ms (hysteresis prevents flicker)"
            raise ValueError(msg)
        return self


class PrimaryUserConfig(_StrictModel):
    """How the primary user is distinguished from other faces.

    The election also has *temporal* hysteresis (AM-8): whoever holds the title
    keeps it unless a challenger scores better by ``switch_margin`` for
    ``switch_patience`` consecutive frames. Without it, two people at comparable
    distance swap the title on a micro-movement — and the title decides whose
    gaze is ignored, so each swap inverts the decision.
    """

    centrality_weight: float = Field(default=1.0, ge=0.0)
    size_weight: float = Field(default=1.0, ge=0.0)
    switch_margin: float = Field(
        default=0.08,
        ge=0.0,
        description="Score lead a challenger needs before a switch is even considered.",
    )
    switch_patience: int = Field(
        default=3,
        ge=1,
        description="Consecutive frames the challenger must keep that lead (1 = no memory).",
    )
    match_distance: float = Field(
        default=0.15,
        gt=0.0,
        le=1.0,
        description="Max normalised distance at which a face is deemed the same one as last frame.",
    )


class MaskingConfig(_StrictModel):
    """Masking layer settings.

    All three strategies are live on the overlay: ``veil`` never captures the
    screen; ``pixelate``/``blur`` transform one local screen capture taken at
    masking time (freeze-frame), kept in RAM only and released when the mask
    lifts (see ``masking.overlay_strategy_is_live`` and
    ``docs/ROADMAP_FLOU_PIXELISATION.md``).
    """

    strategy: MaskStrategyName = "veil"
    opacity: float = Field(default=0.92, ge=0.0, le=1.0)
    blur_radius: int = Field(default=21, ge=1, le=199)
    pixelate_blocks: int = Field(default=24, ge=2, le=256)


class AppConfig(_StrictModel):
    """Top-level application configuration."""

    camera: CameraConfig = Field(default_factory=CameraConfig)
    detection: DetectionConfig = Field(default_factory=DetectionConfig)
    geometry: GeometryConfig = Field(default_factory=GeometryConfig)
    tracking: TrackingConfig = Field(default_factory=TrackingConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    primary_user: PrimaryUserConfig = Field(default_factory=PrimaryUserConfig)
    masking: MaskingConfig = Field(default_factory=MaskingConfig)
