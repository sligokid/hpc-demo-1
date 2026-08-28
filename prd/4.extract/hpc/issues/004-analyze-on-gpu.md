## Parent PRD

`prd/4.extract/hpc/prd.md`

## What to build

Create `analyze-on-gpu.sh`, an interactive `srun` wrapper for single-transcript analysis. It reads the Ollama endpoint from the scratch discovery file, then launches a single `srun` task calling `analyze.py` for the transcript path passed as `$1`. Analogous to the existing `infer-on-gpu.sh`.

See PRD §Implementation Decisions > `analyze-on-gpu.sh`.

## Acceptance criteria

- [ ] `analyze-on-gpu.sh` accepts the transcript file path as its only positional argument
- [ ] Exits non-zero with a descriptive error if no argument is provided
- [ ] Reads the Ollama endpoint from the scratch discovery file (`ollama.endpoint`)
- [ ] Exits non-zero with a descriptive error if the discovery file does not exist
- [ ] Launches a single `srun` task calling `analyze.py --transcript <file> --ollama-host <endpoint>`
- [ ] Uses the same `--account` and `--partition` values as existing scripts
- [ ] Structure mirrors `infer-on-gpu.sh`

## Blocked by

- Blocked by `prd/4.extract/hpc/issues/001-ollama-serve.md` (endpoint discovery file contract)

## User stories addressed

- User story 16
- User story 17
- User story 18
