"""Privacy Guard — anti shoulder-surfing screen privacy guard.

Detects, via the front webcam, when a person other than the primary user looks at
the screen, and automatically masks/blurs sensitive content until they look away.

Honest scope (do not contradict): on a standard display the software cannot change
the *direction* in which light leaves the panel. It only reduces risk by detecting
an observer with the camera and masking content. It does not guarantee invisibility.
"""

__version__ = "0.2.1"
