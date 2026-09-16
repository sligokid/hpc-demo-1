## Parent PRD

`prd/task-2-company-brain/prd.md`

## What to build

Add a `--segments` flag to `2-inference/infer.py` so that every transcription run emits a `segments.json` file alongside the existing `transcript.txt`. The JSON must contain the raw Whisper segment list with `start`, `end`, and `text` per segment. This is the timestamp anchor that all downstream chunking (embed, search, graph) depends on.

See PRD: Chunking Strategy section and Deliverable #1.

## Acceptance criteria

- [ ] `python 2-inference/infer.py --segments --audio <file>` produces `segments.json` in the output directory
- [ ] `segments.json` matches the schema: `[{"start": float, "end": float, "text": str}, ...]`
- [ ] `transcript.txt` continues to be emitted unchanged when `--segments` is used
- [ ] Running without `--segments` produces no `segments.json` (backwards compatible)
- [ ] Smoke test passes on a local audio file (e.g. `2-inference/audio/sligo-triathlon-club-inviting-women-to-try-a-tri.mp3`)

## Blocked by

None — can start immediately.

## User stories addressed

- A new hire searches for a video and gets back the exact timestamp where the answer is spoken — timestamps only exist if `segments.json` is emitted during transcription.
- Every downstream stage (embed, search, graph) depends on Whisper-native timestamps; this issue unblocks all of them.
