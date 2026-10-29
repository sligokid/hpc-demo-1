## Parent PRD

`issues/prd-sop-to-teleprompter.md`

## What to build

Add `11-sop/hpc/teleprompter-sbatch.sh` — a SLURM batch script that runs `teleprompter.py` inside the existing `whisper-hpc.sif` Singularity image on HPC. Follows all established HPC script conventions: `SLURM_SUBMIT_DIR` for project root resolution, `--bind "$PROJECT_ROOT:/workspace"`, and `LD_LIBRARY_PATH` export via `bash -c "..."` wrapper.

## Acceptance criteria

- [ ] `11-sop/hpc/teleprompter-sbatch.sh` exists and follows the project's HPC script conventions
- [ ] Script uses `SLURM_SUBMIT_DIR` to resolve `PROJECT_ROOT`
- [ ] Singularity exec uses `--bind "$PROJECT_ROOT:/workspace"` and `bash -c "..."` wrapper
- [ ] Uses `whisper-hpc.sif` from `/scratch/project_465003359/mcgowank/whisper-hpc.sif`
- [ ] Reads Ollama endpoint from the endpoint file (same pattern as `analyze-sbatch.sh`)
- [ ] Submitted job produces `.teleprompter.md` and `.teleprompter.review.md` in `results/{lang}/`
- [ ] Job completes successfully on a SLURM queue with a real SOP input

## Blocked by

- `issues/003-teleprompter-docker.md`

## User stories addressed

- Stage 3: HPC delivery (Delivery Stages section of PRD)
