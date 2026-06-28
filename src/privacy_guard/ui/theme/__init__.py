"""Design tokens (single source of truth) + a Qt theme controller for QML.

``tokens.py`` is pure data (no Qt) so palette/contrast can be tested headlessly;
``theme_controller.py`` exposes those tokens to QML and handles dark/light +
reduced-motion at runtime.
"""

from __future__ import annotations

from privacy_guard.ui.theme.theme_controller import ThemeController

__all__ = ["ThemeController"]
