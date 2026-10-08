## Parent PRD

`prd/task-2-company-brain/prd.md`

## Problem

`sync/input/en/Workplace Learning Summit - Panel Full Talk.mp4` has never transcribed successfully — 226 attempts, 226 failures, every one with the same error:

```
[en] Workplace Learning Summit - Panel Full Talk.mp4
  INFER ERROR — float division by zero
```

Unlike `firedrill vid.mp4` (see `issues/011-no-audio-track-produces-empty-inference-failure.md`), this file is perfectly valid media with a real audio track:

```
== Workplace Learning Summit - Panel Full Talk.mp4 (300.1 MB)
   hdlr -> vide   mdhd ts=12800  dur=7467520  = 583.4s
   hdlr -> soun   mdhd ts=48000  dur=28005376 = 583.4s
   hdlr -> tmcd
```

583 seconds (9.7 minutes) of 48kHz stereo AAC. Nothing pathological about it — a comparable 311-second file (`dcu slick_LandD.mp4`) transcribes fine. So the `float division by zero` is a genuine software bug, not bad input.

**The stack trace was destroyed** by the bare `except Exception` at `pipeline.py:217`, so we cannot currently tell which division is at fault. Prime suspects, all on the `return_timestamps=True` + chunked path in `2-inference/infer.py`:

- The chunked long-form path in `transformers` (`chunk_length_s=30`, `stride_length_s=5`, set at `infer.py:40-41`) computing an average over an empty set for a chunk.
- `transcribe_with_segments` (`infer.py:52-60`) filtering chunks on `timestamp[0] is not None and timestamp[1] is not None` and then dividing by a count that can reach zero if *every* chunk is filtered out.

Note the interaction: a zero-length `segments` list also silently skips embed+index at `pipeline.py:259` (`if embed_enabled and segments:`), so this failure would quietly produce no search index even if inference appeared to succeed.

## What to build

Fix the `float division by zero` in the Whisper inference path so valid multi-chunk video transcribes successfully.

This issue is **blocked in practice** by `issues/010-log-tracebacks-in-pipeline-errors.md` — land that first, then reproduce on `2-inference/hpc/infer-on-gpu.sh` to get the real stack trace before changing code. Do not guess at the fix.

Steps:

1. With traceback logging in place, reproduce on a GPU node via `srun 2-inference/hpc/infer-on-gpu.sh` against the offending file and capture the stack.
2. Identify the division by zero and fix it at its source.
3. Guard the specific degenerate cases defensively: an empty `segments` list should be an explicit, reported condition rather than a silently-skipped stage.
4. Confirm the fix against both this file and `dcu slick_LandD.mp4` (the working 311-second control), plus at least one `.mp3`.

The 300MB file size is worth keeping in mind — `librosa.load` decodes the entire file into memory as float32 at 16kHz. For a 583-second file that is roughly 37MB, which is fine, but it confirms the full-file decode is happening and is not itself the cause.

## Acceptance criteria

- [ ] `Workplace Learning Summit - Panel Full Talk.mp4` transcribes successfully end to end
- [ ] The root cause is identified from a real stack trace, not inferred
- [ ] The fix is at the source of the division, not a bare `try/except` swallow
- [ ] `dcu slick_LandD.mp4` (311s control) still transcribes successfully
- [ ] A `.mp3` sample still transcribes successfully
- [ ] An empty `segments` result is reported explicitly rather than silently skipping embed+index
- [ ] A regression test covers the multi-chunk case that triggered the division
- [ ] `slog`/logs from the successful run show a non-empty segment count and a non-zero indexed chunk count

## Blocked by

- Blocked by `issues/010-log-tracebacks-in-pipeline-errors.md` (the stack trace is required to locate the division; do not attempt this fix first)

## Related

- `issues/013-bound-retry-loop-for-permanently-failing-files.md` — should land regardless, to bound the retry loop while this is investigated.

## User stories addressed

- A 10-minute panel discussion becomes searchable, as the end-to-end latency and retrieval success criteria in the PRD assume.
- Multi-chunk video longer than the 30-second Whisper window transcribes reliably rather than failing permanently.
