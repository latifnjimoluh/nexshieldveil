# Privacy by design

Privacy Guard processes a webcam feed — the most sensitive kind of input. Its
privacy posture is therefore a **hard design constraint**, enforced by automated
tests (`tests/privacy/`, run on every CI build), not just a promise.

## Guarantees

1. **All processing is strictly local.** No image, landmark, biometric template, or
   derived feature is ever sent over a network. The app opens **no outbound
   connections of any kind**.
   - *Enforced by:* `test_no_outbound_network_during_run` patches `socket.socket`,
     `socket.create_connection`, and `socket.getaddrinfo` to fail the test if any
     network call is attempted during a run.

2. **No image data is written to disk.** Frames exist only in RAM for the duration
   of processing and are then released. Nothing is cached or logged as an image.
   - *Enforced by:* `test_no_files_written_during_run` spies on `open` (and forbids
     `numpy.save`/`savez`) and fails on any write; `test_no_image_files_appear_on_disk`
     runs a full session in an empty directory and asserts no image artifacts appear.

3. **No frame accumulation.** Frame buffers are not retained across iterations, so
   memory does not grow and old frames cannot be exfiltrated later.
   - *Enforced by:* `test_frames_are_not_accumulated` holds `weakref`s to every
     emitted frame and asserts they are garbage-collected (at most the most recent
     one may still be alive). `test_pipeline_retains_no_image_data` asserts the only
     retained per-frame artifact (`FrameResult`) contains scalars, never an array.

4. **No identification of anyone.** The system counts and locates faces and estimates
   whether a gaze points at the screen. It performs **no face recognition** and
   builds **no identity model** — not of the user, not of observers. An observer is
   simply "a non-primary face whose gaze is on the screen", never "who".

5. **No automatic downloads.** The MediaPipe model must be provided locally via a
   configured path. The app never fetches models or any other resource.

## What this means in practice

- You can run Privacy Guard fully offline.
- Nothing leaves your machine; there is no telemetry, account, or cloud component.
- The camera buffer is transient: process, decide, discard.

## Scope reminder

Strong local privacy of *this software* is not the same as guaranteed protection
*of your screen* against every threat. Privacy Guard reduces shoulder-surfing risk;
it does not defend against the threats listed in `docs/LIMITATIONS.md` (e.g. a
camera recording your screen, or an onlooker outside the webcam's field of view).
