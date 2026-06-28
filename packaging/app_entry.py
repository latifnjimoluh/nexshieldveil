"""PyInstaller entry point for the NexShieldVeil desktop application.

Kept tiny on purpose: it just delegates to the QML (MVVM) UI ``main()``. The frozen
build bundles the MediaPipe model under ``models/`` and the QML/i18n assets so the app
works with no setup (see ``privacy_guard.resources.default_model_path`` and the spec).
"""

import sys

from privacy_guard.ui.shell import main

if __name__ == "__main__":
    sys.exit(main())
