## Parent PRD

`issues/prd.md`

## What to build

Convert the Docker image to a Singularity SIF file and write the SLURM job that runs it on LUMI's CPU partition as a self-resubmitting polling loop.

Deliver two artefacts:
- `whisper-sync.sif` — built from the Docker image via `singularity build`, stored at `/scratch/project_465003209/mcgowank/whisper-sync.sif` on LUMI
- `3-sync/hpc/sync-sbatch.sh` — SLURM job definition that runs the SIF via `singularity exec`, binds `/workspace`, mounts the rclone config read-only, and resubmits itself at the end of every run

The SLURM script follows existing repo conventions: `SLURM_SUBMIT_DIR` for project root resolution, `--account project_465003209`, `--partition=small`, and the `bash -c "..."` wrapper pattern used in all other HPC scripts.

See the Modules and Architectural Decisions sections of the parent PRD for the full contract.

## Acceptance criteria

- [ ] `singularity build whisper-sync.sif docker-daemon://whisper-sync:latest` completes successfully
- [ ] SIF is uploaded to `/scratch/project_465003209/mcgowank/whisper-sync.sif` on LUMI
- [ ] `sbatch 3-sync/hpc/sync-sbatch.sh` submits without errors and appears in `squeue` output
- [ ] The job completes one sync cycle (download pass + upload pass + manifest update) and writes a log to `logs/`
- [ ] The job resubmits itself after completion — a second job appears in `squeue` without manual intervention
- [ ] A test audio file placed in the Drive `whisper-sync/input/` folder appears in `/scratch/.../sync/input/` after the next cycle
- [ ] A file placed in `/scratch/.../sync/output/` appears in the Drive `whisper-sync/output/` folder after the next cycle
- [ ] SLURM directives match: `--partition=small`, `--ntasks=1`, `--cpus-per-task=1`, `--mem=4GB`, `--time=00:10:00`
- [ ] Job failure does not permanently break the resubmission chain — the chain restarts after a failed run

## Blocked by

- Blocked by `issues/002-docker-packaging-and-local-test.md`

## User stories addressed

- User story 4 (sync runs as self-resubmitting SLURM job on CPU partition)
- User story 5 (sync job resubmits itself after each run)
- User story 9 (rclone config mounted read-only, chmod 600 on host)
- User story 13 (minimal SLURM resource request)
- User story 18 (SLURM script follows existing repo conventions)
- User story 23 (SLURM job runs sync via `singularity exec` on SIF)
- User story 24 (SIF stored alongside existing `whisper-hpc.sif` in project scratch)
