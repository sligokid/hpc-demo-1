## Parent PRD

`prd/11-sop/prd.md`

## What to build

Wire the SOP stage into `pipeline.py` as a feature-flagged step that runs after the index stage, following the identical pattern used by `sentiment` and `embed`. Add a `sop` block to `pipeline.yaml` with `enabled`, `model`, and `config` keys.

The stage reads the existing `transcript.txt` and `analysis.json` for each file and calls `sop.generate()` (the function extracted from `sop.py`). It respects `max_transcript_words` from config (added in issue 068).

## Acceptance criteria

- [ ] `pipeline.yaml` has a `sop` block: `enabled: true`, `model: qwen2.5:7b`, `config: 11-sop/sop_config.yaml`
- [ ] `pipeline.py` loads `sop_enabled` from config and lazily imports `sop.py` only when enabled (consistent with how `sentiment` and `analyze` are imported)
- [ ] When `sop_enabled=true`, the pipeline calls the SOP stage for each file after the index stage completes
- [ ] When `sop_enabled=false`, the SOP stage is skipped with no error
- [ ] Pipeline output includes a `sop -> {path}` log line on success, matching the format of other stage log lines
- [ ] SOP errors are caught and logged as `SOP ERROR — {exc}` without aborting other files (consistent with `EMBED ERROR` handling)
- [ ] `max_transcript_words` from `pipeline.yaml` is passed through to `sop.generate()`
- [ ] End-to-end smoke test: given a pre-existing `transcript.txt` and `analysis.json` fixture, pipeline with `sop.enabled=true` produces `.sop.md` and `.sop.pdf` (Ollama mocked)

## Blocked by

- Blocked by `issues/todo/070-sop-pdf-generation.md`

## User stories addressed

- User story 9
- User story 11
- User story 12
