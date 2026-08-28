## Parent PRD

`prd/4.extract/hpc/prd.md`

## What to build

Create `ollama-pull.sh`, a standalone setup script (not a SLURM job) that downloads Ollama model weights into scratch storage for air-gapped HPC operation. It accepts a model name as a positional argument (default `llama3`), runs `ollama pull` inside `ollama.sif` with the scratch `ollama-models/` directory bound as `OLLAMA_MODELS`, then verifies the model appears in `ollama list` before exiting. Intended to be run once on a login node or data-transfer node with internet access.

See PRD §Implementation Decisions > `ollama-pull.sh`.

## Acceptance criteria

- [ ] `ollama-pull.sh` accepts an optional positional argument for model name, defaulting to `llama3`
- [ ] Runs `ollama pull <model>` inside `ollama.sif` via `singularity run` with scratch `ollama-models/` bound as `OLLAMA_MODELS`
- [ ] After pull, runs `ollama list` inside the same container and checks that the model name appears in output
- [ ] Exits 0 if model is present in `ollama list`
- [ ] Exits non-zero with a descriptive error message if model is not found in `ollama list`
- [ ] Does not use `#SBATCH` directives (not a SLURM job)

## Blocked by

None - can start immediately.

## User stories addressed

- User story 6
- User story 7
- User story 8
