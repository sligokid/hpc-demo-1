## Parent PRD

`prd/11-sop/prd.md`

## What to build

Create `11-sop/sop.py` — the core SOP generation module. It reads a transcript file and an `analysis.json` file, builds an Ollama prompt that injects the full contents of `11-sop/sop_template.md` alongside the transcript and analysis metadata, calls Qwen via Ollama, and renders the JSON response into a filled Markdown SOP written to `{stem}.sop.md`.

Also create `11-sop/sop_config.yaml` with org metadata fields and a `doc_counter` that auto-increments on each successful generation.

The module must work as a standalone CLI tool (no pipeline required) and skip generation if `.sop.md` already exists.

## Acceptance criteria

- [ ] `11-sop/sop.py` exists and accepts `--transcript`, `--analysis`, `--config`, `--ollama-host`, and `--model` CLI flags
- [ ] `11-sop/sop_config.yaml` exists with `company_name`, `department`, `approver`, `doc_number_prefix`, `doc_counter` fields (placeholder values committed)
- [ ] Prompt sent to Ollama includes: full contents of `sop_template.md`, the transcript text, and title/goals/skills from `analysis.json`
- [ ] Ollama is called with `format: json` and the response is parsed into SOP section keys: `purpose`, `scope`, `responsibilities`, `materials`, `procedure`, `associated_documents`
- [ ] Output `.sop.md` contains all 7 section headings from the template
- [ ] Org fields from `sop_config.yaml` are injected into the header block; fields not derivable from the video remain as `[Insert ...]` placeholders
- [ ] `doc_counter` in `sop_config.yaml` increments by 1 after each successful generation
- [ ] If both `.sop.md` and `.sop.pdf` already exist, Ollama is not called and the function returns early
- [ ] If Ollama returns invalid JSON, the raw response is written to `.sop.md` with a `<!-- WARNING: raw LLM output -->` header rather than crashing
- [ ] `11-sop/test_sop.py` covers: prompt contains transcript + analysis fields; correct Markdown section headings in output; doc counter increments; skip-if-done behaviour; truncation with `max_words > 0`; no truncation with `max_words=0`
- [ ] All tests pass with `requests.post` mocked — no live Ollama instance required
- [ ] `11-sop/local/run.sh` runs `sop.py` for a single transcript/analysis pair

## Blocked by

- Blocked by `issues/todo/068-configurable-transcript-truncation.md`

## User stories addressed

- User story 1
- User story 2
- User story 3
- User story 6
- User story 7
- User story 8
- User story 10
- User story 13
- User story 14
- User story 19
- User story 20
