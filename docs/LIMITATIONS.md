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
| 3 | **The brief window before masking** | Masking engages after `trigger_ms` of detected gaze, **plus** a short EMA smoothing warm-up (~1-2 frames), so the effective delay is a little longer than `trigger_ms`. Content is visible during that window (tunable in **Settings**: the masking delay and the new *Reactivity* slider, which is that EMA — set it to the maximum to drop the smoothing entirely; the delay is never zero in practice). |
| 4 | **Reflections** | Glass, glossy surfaces, a mirror, or the onlooker's own glasses can leak the screen without any face looking at it directly. |
| 5 | **Long-range zoom / telephoto** | A distant observer with a zoom lens may be unresolved or out of frame. |
| 6 | **Poor conditions / occlusion** | Bad lighting, masks, hats, extreme angles, or a covered camera cause missed detections (false negatives). |
| 7 | **A disabled or absent camera** | With no camera (or the `vision` extra/model missing) the app runs in degraded mode and **never masks**. |
| 8 | **Off-screen leakage** | It protects the screen content only — not what you say, type audibly, or print. |

## Blur / pixelate specifics (freeze-frame masking)

- **The masked image is frozen.** Blur/pixelate transform *one* capture taken at
  masking time; the screen underneath keeps living but stays hidden behind that
  frozen picture. A notification arriving *while* masked is therefore covered
  (a privacy plus), but what you see under the mask is a snapshot, not live blur.
- **Blur reduces readability; it is not encryption.** A weak blur over very
  large text (a headline, a huge font) can remain guessable. Keep the default
  strength or raise it; when in doubt, the opaque veil hides the most.
- **Some situations yield nothing to blur.** A locked screen, DRM-protected
  content, or an OS refusing capture (e.g. Wayland without a portal) produces a
  blank or failed capture — the app then falls back to the **opaque veil**, so
  protection never silently drops to "nothing".

## Locked sessions

- **Windows and Linux (logind):** watching pauses while the session is locked and
  resumes on unlock, so the camera is released and its indicator goes dark. A
  session you had paused yourself stays paused.
- **macOS: not implemented.** The lock notification needs a native API PySide6
  does not expose, so watching keeps running (camera on) while the screen is
  locked. Same on any desktop without the logind signals. Nothing is protected
  less — there is simply nothing to protect behind a lock screen — but the CPU,
  battery and camera indicator cost stays.

## Screen geometry and multiple monitors

- **The decision models one screen**: the plane the camera sits above. Its size is
  read from the operating system at startup when the value is believable (EDID
  data is often missing or wrong), otherwise the configured one is used — and a
  size you set yourself in the TOML always wins.
- **The masking covers every screen**, since v0.3.0. So on a multi-monitor desk
  the app hides all your screens, but it judges "is this gaze pointing at my
  screen?" against the primary one only. Someone reading your *second* monitor
  from an angle the primary-screen model does not cover may not trigger masking.
- Camera position matters too: `camera_above_screen_mm` assumes the webcam sits
  above the screen it is modelling. An external webcam parked elsewhere makes the
  geometry wrong in ways no default can guess.

## Idle back-off specifics

- **When nobody has been in front of the camera for a while** (30 s by default),
  the capture rate drops to 5 fps to spare CPU and battery. A person appearing
  is then noticed up to one idle frame later (~200 ms), which is added to the
  masking delay — that is a floor on how fast the app *starts* reacting, never
  on how fast it reacts once someone is there: a single detected face restores
  the full rate immediately.
- Set `camera.idle_after_ms = 0` to keep the full rate at all times.

## Walk-away lock specifics

- **It reacts to absence, not to identity.** When enabled, the screen hides after
  the configured delay with no face in view, and lifts as soon as *a* face is
  back — we do not, and will not, check that it is **your** face. If someone sits
  down while you are away, the screen unhides for them like it would for you.
  What the lock buys you is the window in between, which the observer detection
  structurally cannot cover: with a single face in frame, that face is by
  definition the primary user, so its gaze is ignored.
- **It is off by default.** It changes when your screen hides, so it is your call.
- **A blind camera looks like an empty room.** A covered lens, a very dark room,
  or a face the detector cannot resolve all read as "nobody there" and will
  eventually mask the screen. That is the safe direction to fail in, but it does
  mean the lock can hide your screen while you are sitting right in front of it.

## Gaze estimation: head pose, and optionally the iris

- **By default the gaze is the head pose.** Someone who keeps their head straight
  and moves only their *eyes* toward your screen is read as "not looking" — a
  real miss the detection cannot currently catch.
- An **experimental** iris correction exists (`detection.use_iris`, off by
  default). It has **not been validated on real hardware**, and it is not free
  to be wrong: an incorrect offset moves the gaze ray and can create false
  positives where there were none. Treat it as something to measure, not as an
  improvement you can assume.

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
