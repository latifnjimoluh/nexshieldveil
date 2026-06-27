# Architecture

Privacy Guard strictly separates **pure decision logic** (testable without any
hardware) from **adapters** (camera, screen, UI). The pipeline depends only on
interfaces, so every decision path is exercised headless in CI.

## Data flow

```
 ┌──────────┐   Frame    ┌────────┐  [FaceObservation]  ┌──────────┐
 │ capture  │──────────▶ │ vision │────────────────────▶│ geometry │
 │FrameSource│           │Detector│                     │ gaze hits │
 └──────────┘            └────────┘                     │  screen?  │
                                                        └─────┬────┘
                                                  observer_present (bool)
                                                              │
                                          ┌───────────────────▼────────┐
                                          │ tracking (EMA smoothing)    │
                                          └───────────────────┬────────┘
                                                              │
                                          ┌───────────────────▼────────┐
                                          │ policy (hysteresis FSM)     │
                                          │ CLEAR→DETECTED→MASKED→CLEAR │
                                          └───────────────────┬────────┘
                                                       is_masked (bool)
                                                              │
                                          ┌───────────────────▼────────┐
                                          │ overlay (Renderer) + masking│
                                          └─────────────────────────────┘
```

## Modules

| Module | Kind | Responsibility | Hardware? |
|---|---|---|---|
| `config` | pure | Pydantic schema + TOML loading, bounds validation | no |
| `geometry` | pure | Gaze vectors, ray/plane intersection, screen targeting, primary-user pick | no |
| `tracking` | pure | EMA / 1D Kalman smoothing | no |
| `policy` | pure | Hysteresis state machine (anti-flicker) | no |
| `masking` | pure | Image transforms: veil / pixelate / blur | no |
| `capture` | adapter | `FrameSource`: webcam / video file / **synthetic** | webcam optional |
| `vision` | adapter | `FaceDetector`: MediaPipe wrapper / **scripted** | MediaPipe optional |
| `overlay` | adapter | `Renderer`: Qt overlay / **recording** | display optional |
| `app` | wiring | `PrivacyGuardPipeline` orchestration + CLI | no (interfaces) |

The **bold** implementations are the headless test doubles that let the real
geometry/policy/masking code run with no camera or display.

## Key interfaces (injection seams)

- **`FrameSource`** — `read() -> Frame | None`, `close()`, `is_available`.
  `SyntheticFrameSource` produces deterministic in-RAM frames; `WebcamFrameSource`
  and `VideoFileFrameSource` wrap OpenCV and raise a clear error if it's absent.
- **`FaceDetector`** — `detect(frame) -> list[FaceObservation]`. `ScriptedFaceDetector`
  replays a fixed script per frame; `MediaPipeFaceDetector` does real landmark +
  `solvePnP` head-pose estimation when MediaPipe/OpenCV and a model are present.
- **`Renderer`** — `set_masked(bool)`, `is_masked`. `RecordingRenderer` records
  transitions (test double + observable hook); `QtOverlayRenderer` shows the real
  transparent, always-on-top, click-through window.

## The decision state machine

`policy.DecisionStateMachine` is timestamp-driven (frame-rate independent) with two
independent thresholds:

- `CLEAR → OBSERVER_DETECTED` when an observer is first seen.
- `OBSERVER_DETECTED → MASKED` after `trigger_ms` of sustained observer gaze
  (`→ CLEAR` if the observer leaves first).
- `MASKED → CLEAR` after `release_ms` of sustained absence (`release_ms >=
  trigger_ms`), giving hysteresis that prevents on/off flicker.

## Coordinate frame (geometry)

Right-handed, camera at the origin: `+x` right, `+y` up, `+z` toward the viewer.
The screen lies in the plane `z = 0`, below the camera. A face sits at `z > 0`;
`gaze_vector(0, 0)` is `(0, 0, -1)` (looking into the screen). "Gaze points at the
screen" = the gaze ray's intersection with `z = 0`, clamped to the screen rectangle,
is within `gaze_tolerance_deg` of the gaze direction.

## Honesty & degradation

Head-pose/gaze from a webcam is approximate (~1.5–3° error), so tolerances are
generous and configurable; we never claim sub-degree accuracy. Every adapter
degrades gracefully: missing camera, MediaPipe, model, or display all produce a
logged warning and a working (if limited) app rather than a crash.

## Future evolutions (out of scope here)

- **Approach B** — gaze-contingent foveal rendering.
- **Approach C** — temporal psychovisual modulation with synchronized glasses.
- GPU real-time blur of arbitrary on-screen content (MVP veils/pixelates a capture).

These require additional hardware and/or rendering pipelines and are deliberately
not implemented; see `docs/ROADMAP.md`.
