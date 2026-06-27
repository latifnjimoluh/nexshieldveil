# Limitations — what Privacy Guard does NOT protect against

Privacy Guard **reduces** the risk of shoulder surfing. It does **not** guarantee
that your screen is private. Read this before relying on it.

## The fundamental physical limit

On a standard LCD/OLED display, software controls only the **value** (colour/
intensity) of each pixel — never the **direction** in which light leaves the panel.
Any image readable head-on is also emitted sideways. So **no software can make a
screen "invisible from the side"** by manipulating pixels. True narrow-viewing-angle
solutions are *optical* (e.g. 3M privacy films, HP Sure View), not software.

Privacy Guard works the only way software can: **detect an observer via the camera
and hide the content.** This implies the limits below.

## Not protected

| # | Threat | Why Privacy Guard can't stop it |
|---|---|---|
| 1 | **A camera/phone recording your screen** | A lens is not a gaze; the webcam can't tell it's being filmed. |
| 2 | **An onlooker outside the webcam's field of view** | Detection only covers roughly the camera's ~90–180° cone. Someone behind or to the extreme side is invisible to it. |
| 3 | **The brief window before masking** | Masking engages after `trigger_ms` of detected gaze, **plus** a short EMA smoothing warm-up (~1-2 frames), so the effective delay is a little longer than `trigger_ms`. Content is visible during that window (tunable via `trigger_ms` and `tracking.smoothing_alpha`; set `alpha = 1.0` to drop the EMA, but it is never zero in practice). |
| 4 | **Reflections** | Glass, glossy surfaces, a mirror, or the onlooker's own glasses can leak the screen without any face looking at it directly. |
| 5 | **Long-range zoom / telephoto** | A distant observer with a zoom lens may be unresolved or out of frame. |
| 6 | **Poor conditions / occlusion** | Bad lighting, masks, hats, extreme angles, or a covered camera cause missed detections (false negatives). |
| 7 | **A disabled or absent camera** | With no camera (or the `vision` extra/model missing) the app runs in degraded mode and **never masks**. |
| 8 | **Off-screen leakage** | It protects the screen content only — not what you say, type audibly, or print. |

## Accuracy caveats

- Webcam gaze estimation typically carries **1.5–3° of error**; we do **not** claim
  sub-degree precision. The "looking at screen" tolerance is deliberately generous
  and configurable, which trades some false positives for fewer misses.
- **False positives** (masking when no one is snooping) can happen with head
  movements or a second person merely present but not reading. Hysteresis and
  conservative thresholds reduce, but don't eliminate, these.
- **False negatives** (failing to mask a real snooper) can happen in the conditions
  above. Treat Privacy Guard as a helpful layer, not a guarantee.

## Honest summary

Use Privacy Guard to make casual shoulder surfing meaningfully harder. Do **not**
use it as your sole protection for highly sensitive material — combine it with an
optical privacy filter, screen positioning, and good situational awareness.
