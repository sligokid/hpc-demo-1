## Parent PRD

`issues/prd.md`

## What to build

`12-tts/local/run.sh` — a shell script that runs `tts.py` directly (no Docker, no SLURM) against any `{stem}.teleprompter.md` file. Accepts the teleprompter file as a positional argument, derives lang and stem from the path, resolves the project root, and calls `tts.py` with the correct arguments. Respects `OLLAMA_HOST` (default `localhost:11434`) and `VOICE` environment variables.

Follows the exact pattern of `11-sop/local/run.sh` and `11-sop/local/run-teleprompter.sh`.

## Acceptance criteria

- [ ] `12-tts/local/run.sh` exists and is executable
- [ ] Accepts a single positional arg: path to a `.teleprompter.md` file
- [ ] Derives `LANG` and `STEM` from the file path
- [ ] Calls `tts.py --input … --output … --ollama-host … --voice …` with correct paths
- [ ] `OLLAMA_HOST` defaults to `localhost:11434` if not set
- [ ] `VOICE` defaults to `Freya` (or another sensible default) if not set
- [ ] Usage error printed if no argument supplied

## Blocked by

- `issues/tts/075-tts-core.md`

## User stories addressed

- User story 3
- User story 7
- User story 8
