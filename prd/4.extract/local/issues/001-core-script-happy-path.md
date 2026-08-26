# 001 — Core script: happy path

## Parent PRD

`prd/4.metadata/prd.md`

## What to build

A standalone `analyze.py` script that accepts a transcript file path via `--transcript` and an optional `--model` flag (default `llama3`), sends a structured prompt to the Ollama `/api/generate` endpoint with `format: "json"`, and prints a pretty-printed JSON object to stdout containing exactly five fields: `title`, `description`, `tags`, `goals`, and `skills`.

This is the core tracer bullet. All other slices build on it.

## Acceptance criteria

- [ ] `python analyze.py --transcript path/to/transcript.txt` prints valid JSON to stdout
- [ ] JSON contains all five fields: `title` (string), `description` (string), `tags` (list), `goals` (list), `skills` (list)
- [ ] `--model llama3` is the default; passing `--model mistral` uses mistral instead
- [ ] Output is pretty-printed (human-readable in a terminal)
- [ ] Script calls `http://localhost:11434/api/generate` with `format: "json"` in the request body
- [ ] The prompt instructs the model to return only the five required fields with the correct types
- [ ] Script exits 0 on success

## Blocked by

None — can start immediately.

## User stories addressed

- User story 1: pass a transcript file, receive structured JSON
- User story 3: metadata includes a concise title
- User story 4: metadata includes a 2-3 sentence description
- User story 5: metadata includes a list of tags
- User story 6: metadata includes a list of learning goals
- User story 7: metadata includes a list of skills
- User story 8: all five fields present in every response
- User story 9: model configurable via `--model` flag
- User story 10: `llama3` is the default model
- User story 15: JSON output is pretty-printed
- User story 16: metadata reflects actual transcript content
- User story 17: no dependency on cloud API or API key
- User story 18: script is independent of `infer.py` and `train.py`
