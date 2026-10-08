## Parent PRD

`prd/task-2-company-brain/prd.md`

## Problem

`sync/input/en/firedrill vid.mp4` has never transcribed successfully — 226 attempts, 226 failures:

```
[en] firedrill vid.mp4
  INFER ERROR — 

Finished: 0/1 succeeded, 1 failed.
```

The empty exception message gave nothing away, but the file itself does. Parsing its MP4 box structure directly shows a single media track, and it is **video only**:

```
== firedrill vid.mp4 (2.2 MB)
   hdlr -> vide
   mdhd ts=15360 dur=134656 = 8.8s
```

There is no `soun` handler and no `smhd` box anywhere in the file. The file is an 8.8-second video with no audio stream at all.

`librosa.load` (`2-inference/infer.py:34`) therefore returns a zero-length array, and the failure surfaces downstream as an exception with an empty `str()`. The pipeline reports the bare message with no indication that the input has no audio, so the file looks like a transient glitch rather than a permanently impossible input.

Worse, because no `.done` sidecar is written on failure, this file is resubmitted every 10 minutes indefinitely — see `issues/013-bound-retry-loop-for-permanently-failing-files.md`.

## What to build

Detect and clearly report media files that have no usable audio stream, instead of letting them fail deep inside the inference stack with a blank error.

Add an explicit audio-presence check before transcription:

- After loading audio in `2-inference/infer.py`, verify the array is non-empty and contains non-silent samples. A zero-length array, or one whose peak amplitude is zero, means there is nothing to transcribe.
- Raise a **named, self-describing exception** (e.g. `NoAudioStreamError`) with a message that names the problem and the file, rather than an exception with an empty `str()`.
- `pipeline.py` catches it as a distinct case and reports `SKIP — no audio stream in <file>`, so the operator immediately understands the file is unprocessable rather than temporarily broken.
- Because this is a permanent, deterministic property of the file, it should be treated as immediately-permanently-failing, not retried the retry budget times.

Consider whether the sync stage should warn at upload time instead — `4-file-sync/sync.sh` sees new arrivals first and could reject or flag video-only files before they reach the GPU queue. That is a larger change; the inference-side check is the minimum viable fix.

## Acceptance criteria

- [ ] `2-inference/infer.py` checks for a usable audio stream before running Whisper
- [ ] A zero-length or fully-silent audio array raises a named exception with a message naming the file and the reason
- [ ] `pipeline.py` reports `SKIP — no audio stream` for this case, distinct from a generic inference error
- [ ] `firedrill vid.mp4` is reported as having no audio stream rather than failing with an empty error
- [ ] A file with a valid but quiet audio track is still transcribed (the silence check must not reject legitimate quiet recordings)
- [ ] The no-audio case is classified as a permanent failure for the purposes of `issues/013-bound-retry-loop-for-permanently-failing-files.md`
- [ ] A regression test covers a video-only input and asserts the named exception, not a generic failure

## Blocked by

- None - can start immediately.

## Related

- `issues/010-log-tracebacks-in-pipeline-errors.md` — makes this failure legible in logs; independent, but the two compound well.
- `issues/013-bound-retry-loop-for-permanently-failing-files.md` — stops the resubmission loop regardless of this fix.

## User stories addressed

- An operator uploading a video with no audio track gets a clear explanation instead of an unexplained failure that repeats every ten minutes.
- Video-only files never reach the GPU, so they cannot consume transcription capacity.
