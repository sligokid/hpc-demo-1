## Parent PRD

`prd/4.extract/hpc/prd.md`

## What to build

Create `analyze-batch.sh`, a SLURM array job that processes a directory of transcript `.txt` files in parallel using the persistent Ollama service. It reads the Ollama endpoint from the scratch discovery file, maps `SLURM_ARRAY_TASK_ID` to a transcript file, calls `analyze.py --transcript <file> --ollama-host <endpoint>`, and writes output to `metadata/<basename>.json`. Fails immediately with a clear error if the discovery file does not exist.

See PRD §Implementation Decisions > `analyze-batch.sh` and §Directory conventions.

## Acceptance criteria

- [ ] `analyze-batch.sh` is a valid SLURM array batch script with `#SBATCH` directives using the same `--account` and `--partition` as existing scripts
- [ ] Logs per-task stdout/stderr to `logs/%A_%a.out` following the existing naming convention
- [ ] Reads the Ollama endpoint from the scratch discovery file (`ollama.endpoint`)
- [ ] Exits non-zero with a descriptive error message if the discovery file does not exist
- [ ] Maps `SLURM_ARRAY_TASK_ID` to a `.txt` file in the `transcripts/` directory
- [ ] Calls `analyze.py --transcript <file> --ollama-host <endpoint>`
- [ ] Writes JSON output to `metadata/<basename>.json` (e.g. `transcripts/foo.txt` → `metadata/foo.json`)
- [ ] Creates `metadata/` directory if it does not exist
- [ ] Supports `--dependency=after:<service_jobid>` for coordinated submission (documented in a comment)

## Blocked by

- Blocked by `prd/4.extract/hpc/issues/001-ollama-serve.md` (endpoint discovery file contract)

## User stories addressed

- User story 11
- User story 12
- User story 13
- User story 14
- User story 15
- User story 23
- User story 28
