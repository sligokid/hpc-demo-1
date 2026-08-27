## Parent PRD

`prd/4.extract/hpc/prd.md`

## What to build

Create `ollama-serve.sh`, a SLURM batch script that runs a persistent Ollama inference service on a GPU node inside a Singularity container. The script allocates one GPU node, starts Ollama with ROCm passthrough inside `ollama.sif`, runs a health-check loop until the HTTP API responds, then atomically writes `$HOSTNAME:11434` to a well-known scratch discovery file. It stays alive for a configurable wall time (default 8 hours) and removes the discovery file via a `trap` on `EXIT`/`TERM`.

Also covers building `ollama.sif` from `ollama/ollama:rocm` — this requires human validation of ROCm driver compatibility against the cluster before use in production.

See PRD §Implementation Decisions > `ollama-serve.sh`, §Key architectural decisions, and §Directory conventions.

## Acceptance criteria

- [ ] `ollama-serve.sh` is a valid SLURM batch script with `#SBATCH` directives using the same `--account` and `--partition` as existing scripts
- [ ] Requests sufficient GPU memory to load llama3 8B (~5 GB)
- [ ] Wall time defaults to 8 hours, configurable via a variable at the top of the script
- [ ] Starts Ollama inside `ollama.sif` using `singularity run --rocm` with scratch `ollama-models/` bound as `OLLAMA_MODELS`
- [ ] Health-check loop polls `GET /api/tags` via `curl`; times out after 120 seconds and exits non-zero if Ollama never becomes ready
- [ ] Endpoint discovery file is written atomically (write to temp file, then `mv`) only after health check passes
- [ ] Discovery file contains `$HOSTNAME:11434`
- [ ] Prints a clear error and exits non-zero if port 11434 is already in use on the allocated node
- [ ] `trap` on `EXIT` removes the discovery file
- [ ] `singularity pull` command for building `ollama.sif` from `ollama/ollama:rocm` is documented in a comment at the top of the script or in a companion note
- [ ] Human validates `ollama.sif` ROCm version against cluster driver before production use (HITL gate)

## Blocked by

None - can start immediately.

## User stories addressed

- User story 1
- User story 2
- User story 3
- User story 4
- User story 5
- User story 19
- User story 20
- User story 21
- User story 22
- User story 26
- User story 27
- User story 28
- User story 29
