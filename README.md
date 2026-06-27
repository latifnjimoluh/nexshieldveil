# Privacy Guard

> **Naming:** the repository/product is **NexShieldVeil**; the Python
> distribution and import package are `privacy-guard` / `privacy_guard`. They refer
> to the same project.

**Anti shoulder-surfing screen privacy guard.** Privacy Guard watches your front
webcam and, when it detects that *someone other than you* is looking at your
screen, automatically veils the content with an opaque overlay until they look
away.

> The live overlay applies an **opaque veil**. Pixelate/blur are implemented and
> tested as image-transform building blocks (`privacy_guard.masking`) for a planned
> capture-based masking path, but are **not yet wired to the live overlay**;
> selecting them at runtime falls back to the veil with a warning.

> ### Honest scope — read this first
> On a standard display, **software cannot change the direction in which light
> leaves the screen.** There is no way to make a screen "invisible from the side"
> by manipulating pixels — that is a physical limit, not a missing feature.
>
> Privacy Guard therefore works the only way software can: it **detects an observer
> with the camera and hides the content**. It **reduces** the risk of shoulder
> surfing; it does **not guarantee** privacy. See [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md).

It never identifies *who* anyone is — it only counts/locates faces and estimates
whether a gaze points at the screen. All processing is **strictly local**; no image
ever touches the disk or the network. See [`docs/PRIVACY.md`](docs/PRIVACY.md).

---

## How it works

```
webcam ──▶ capture ──▶ vision ──▶ geometry ──▶ tracking ──▶ policy ──▶ overlay
        (FrameSource) (faces +   (gaze hits   (smoothing) (hysteresis  (mask on/off)
                       landmarks)  screen?)                 state machine)
```

1. **capture** grabs frames (webcam, video file, or synthetic — injectable).
2. **vision** (MediaPipe Face Landmarker) finds faces + iris/landmarks.
3. **geometry** picks the primary user (most central/closest face) and tests, for
   every *other* face, whether its estimated gaze points at the screen.
4. **tracking** smooths the per-frame signal to cut jitter.
5. **policy** is a hysteresis state machine: it masks only after an observer has
   been looking for `trigger_ms`, and unmasks only after they've been gone for
   `release_ms` — this prevents flicker.
6. **overlay** is a transparent, always-on-top, click-through Qt window that veils
   the screen (opaque veil; see the masking note above).

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design.

---

## Installation

Requires **Python 3.11+**.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate

# Core only (pure logic; what CI runs):
pip install -e .

# With the webcam + UI runtime (to actually run the app):
pip install -e ".[vision,ui]"

# Developer tooling (tests, lint, types):
pip install -e ".[dev]"
```

### The MediaPipe model

Detection needs a local **Face Landmarker** model file. Privacy Guard **never
downloads anything** — you supply the path. Download `face_landmarker.task` from
the MediaPipe model card and point the config at it:

```toml
[detection]
model_path = "models/face_landmarker.task"
```

Without a model (or without the `vision` extra), the app still starts and runs in a
**degraded mode**: it cannot see faces, so it never masks, but it does not crash.

---

## Running

```bash
# With defaults (looks for a webcam, MediaPipe model, and a display):
privacy-guard

# With a config file and verbose logging:
privacy-guard --config config.example.toml --verbose
```

Copy [`config.example.toml`](config.example.toml) and tune sensitivity, timings,
screen size, and masking style. Every threshold is configurable and conservative by
default.

> Need an interactive login or to run a command in this shell? Prefix it with `!`.

---

## Development

```bash
ruff check . && ruff format --check .      # lint + format
mypy src/privacy_guard/config src/privacy_guard/geometry \
     src/privacy_guard/tracking src/privacy_guard/policy src/privacy_guard/masking
pytest -m "not slow and not requires_hardware"   # fast suite
pytest -m privacy                                 # privacy guarantees
pytest -m performance                             # benchmarks
pytest --cov=privacy_guard --cov-report=term-missing
pre-commit install                                # enable hooks
```

The whole suite runs **headless** (no camera, no display) by injecting
`SyntheticFrameSource` + `ScriptedFaceDetector`, so CI is deterministic.

---

## Project layout

```
src/privacy_guard/
  capture/  vision/  geometry/  tracking/  policy/  masking/  overlay/  config/
  app.py
tests/  unit/ component/ integration/ system/ performance/ privacy/
docs/   ROADMAP  ARCHITECTURE  PRIVACY  LIMITATIONS
```

## License

MIT.
