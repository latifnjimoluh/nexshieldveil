# Privacy by design

Privacy Guard processes a webcam feed — the most sensitive kind of input. Its
privacy posture is therefore a **hard design constraint**, enforced on every CI
build by two complementary layers in `tests/privacy/`:

- **Behavioural tests** run a full synthetic session under monkeypatched
  `socket`/`open`/`numpy.save` and fail on any network or disk write.
- **A static (AST) guard** (`test_source_hygiene.py`) parses *every* file in
  `src/` — including the real MediaPipe/OpenCV/Qt adapters that aren't importable
  in CI — and fails if any of them imports a network/persistence module or calls a
  disk-write/network function. This is what backs the guarantees for the real
  hardware paths, which the behavioural tests cannot execute headlessly.

## Guarantees

1. **No image, landmark, or biometric data ever leaves your machine.** Frames and any
   derived features are processed strictly locally and never transmitted. The
   *detection/masking path* opens **no outbound connection of any kind**.
   - *Enforced by:* `test_no_outbound_network_during_run` patches `socket.socket`,
     `socket.create_connection`, and `socket.getaddrinfo` to fail if any network call
     happens during a run; the static AST guard forbids network imports in every
     source file **except** the single quarantined updater (see the exception below);
     and `test_updater_is_isolated_from_camera_and_biometrics` proves that updater
     cannot import any camera/vision/frame code, so it can never see — let alone send —
     biometric data.

   > **The one documented network exception: the optional self-updater.**
   > The desktop app can check GitHub for a newer version and, *only on your explicit
   > click*, download the installer. This is the **sole** module allowed to use the
   > network (`privacy_guard/update/checker.py`), it sends **no data** (anonymous
   > read-only GETs), and it is mechanically isolated from the camera. You can turn off
   > the automatic check in **Paramètres** (it is the only thing that ever contacts the
   > network, and it is easy to verify/block at your firewall).

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

5. **No model auto-download.** The MediaPipe model is either provided locally via a
   configured path or **embedded inside the packaged build**. The app never fetches a
   model at runtime. (The optional updater fetches an *installer*, never a model, and
   only on your click — see exception above.)

## Third-party libraries (honest caveat)

The guarantees above cover **our** code. A bundled third-party library can have its
own behaviour: in particular, **MediaPipe (Google) may attempt to emit its own
telemetry** ("clearcut" lines you can see in the logs). This is not our code and sends
none of your frames, but it is an outbound attempt by a dependency. If you need an
absolute guarantee, **block the application's network access at your firewall** — the
detection/masking works fully offline; only the optional update check needs the
network.

## What this means in practice

- You can run NexShieldVeil fully offline (detection/masking never needs the network).
- No frame, landmark, or biometric data ever leaves your machine.
- The only first-party network use is the **optional, disableable** update check.
- The camera buffer is transient: process, decide, discard.

## Scope reminder

Strong local privacy of *this software* is not the same as guaranteed protection
*of your screen* against every threat. Privacy Guard reduces shoulder-surfing risk;
it does not defend against the threats listed in `docs/LIMITATIONS.md` (e.g. a
camera recording your screen, or an onlooker outside the webcam's field of view).
