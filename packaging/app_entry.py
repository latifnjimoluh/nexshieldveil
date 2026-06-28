"""PyInstaller entry point for the NexShieldVeil desktop application.

Kept tiny on purpose: it just delegates to the real UI ``main()``. The frozen build
bundles the MediaPipe model under ``models/`` so the app works with no setup (see
``privacy_guard.resources.default_model_path``).
"""

import sys

from privacy_guard.ui.control_window import main

if __name__ == "__main__":
    sys.exit(main())
