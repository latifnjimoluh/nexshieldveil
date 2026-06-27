# Test fixtures

Frames and observation scripts are **generated deterministically in code** (see
`tests/conftest.py`), never loaded from or written to disk. This keeps the test
suite reproducible and consistent with the project privacy rule: **no image data
is ever persisted**.

No binary video clips are stored here on purpose. The `VideoFileFrameSource` path
is covered by component tests guarded on OpenCV availability; deterministic
end-to-end behaviour is proven via `SyntheticFrameSource` + `ScriptedFaceDetector`.
