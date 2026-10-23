## Parent PRD

`prd/11-sop/prd.md`

## What to build

Replace the hardcoded `_MAX_TRANSCRIPT_WORDS = 3000` constant in `3-analyze/analyze.py` with a configurable `max_words` parameter. The pipeline reads `max_transcript_words` from `pipeline.yaml` and passes it through to `analyze()`. A value of `0` means no truncation (unlimited). The default for both the function and CLI is `0`. Local `pipeline.yaml` sets `max_transcript_words: 3000` to cap runs for speed. HPC requires no override — the unlimited default applies automatically.

This unblocks the SOP stage, which needs full-transcript access on HPC, and fixes the silent content loss that affects long videos in the existing analyze stage.

## Acceptance criteria

- [ ] `analyze()` in `3-analyze/analyze.py` accepts a `max_words=3000` parameter (default preserves existing local behaviour)
- [ ] When `max_words=0`, the full transcript is passed to Ollama without truncation
- [ ] `pipeline.yaml` gains a top-level `max_transcript_words: 3000` key
- [ ] `pipeline.py` reads `max_transcript_words` from config and passes it to `analyze()`
- [ ] Existing tests for `analyze.py` still pass
- [ ] New tests assert: truncation occurs when `max_words=3000` and a longer transcript is supplied; no truncation occurs when `max_words=0`

## Blocked by

None — can start immediately.

## User stories addressed

- User story 11
- User story 12
