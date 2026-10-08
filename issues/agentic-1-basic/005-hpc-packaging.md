## Parent PRD

`issues/prd-v1.md`

## What to build

Create the HPC launch scripts that wrap the Singularity `exec` call with correct bind mounts and environment variables, and convert the Docker image to a SIF file. After this issue, the agent runs on HPC via an `srun` interactive session with a single command.

**`10-agent/hpc/run.sh` — Singularity launch script**
Follows the `srun` interactive pattern from `2-inference/hpc/infer-on-gpu.sh`. Uses `$PWD` (not `SLURM_SUBMIT_DIR`) since this is an interactive session, not an sbatch job. Sets `PROJECT_ROOT` relative to the script location. Constructs the `singularity exec` call with:
- `--bind "$PROJECT_ROOT:/workspace"` — binds project root (same as Docker)
- `--bind "$PROJECT_ROOT/.hf_cache:$HF_HOME"` — bind-mounts the HuggingFace cache
- `--env QDRANT_HOST`, `--env OLLAMA_HOST` — passed through from the calling environment
- `bash -c "export LD_LIBRARY_PATH=...; python /workspace/10-agent/agent.py"` — uses the bash wrapper pattern required for GPU library paths inside Singularity (same pattern as existing HPC scripts in this repo)

**`10-agent/hpc/build-sif.sh` — SIF conversion script**
Converts the Docker image `slickplus/agent:latest` to a Singularity SIF file using `singularity build`. Outputs to `/scratch/project_465003359/mcgowank/agent.sif`, following the naming and storage convention of the existing `whisper-hpc.sif`. Requires Docker image to be built first (`004-docker-packaging.md`).

**Usage on HPC:**
```bash
srun --pty --gres=gpu:1 bash
export QDRANT_HOST=localhost:6333
export OLLAMA_HOST=localhost:11434
bash 10-agent/hpc/run.sh
```

## Acceptance criteria

- [ ] `bash 10-agent/hpc/build-sif.sh` converts the Docker image to `agent.sif` at the correct scratch path
- [ ] `bash 10-agent/hpc/run.sh` (inside an `srun` interactive session) starts the agent and presents a `>` prompt
- [ ] The SIF correctly bind-mounts `.hf_cache` — model is not re-downloaded on each run
- [ ] `QDRANT_HOST` and `OLLAMA_HOST` env vars are passed through into the container correctly
- [ ] The bash wrapper (`bash -c "export LD_LIBRARY_PATH=...; python ..."`) is used so GPU libraries are available inside the container
- [ ] `PROJECT_ROOT` is resolved using `$PWD` (srun interactive pattern), not `SLURM_SUBMIT_DIR`
- [ ] Script works when called from inside `10-agent/hpc/` and from the project root

## Blocked by

- Blocked by `issues/004-docker-packaging.md`

## User stories addressed

- User story 2 (`singularity exec agent.sif` inside `srun` interactive session)
- User story 3 (env var configuration works in SIF)
- User story 4 (HF cache bind-mounted in Singularity)
- User story 21 (HPC launch script wraps singularity exec)
