## Parent PRD

`prd/11-sop/prd.md`

## What to build

Deploy the SOP stage to HPC. Convert the Docker image to a Singularity `.sif` file stored in scratch alongside `whisper-hpc.sif`. Provide a SLURM array job that processes all pending transcripts in parallel and an interactive `srun` wrapper for single-file use. Add an HPC pipeline config that sets `max_transcript_words: 0` and a larger Qwen model.

All scripts follow the established conventions: `SLURM_SUBMIT_DIR` for project root, `--bind "$PROJECT_ROOT:/workspace"`, and `singularity exec ... bash -c "..."` for `LD_LIBRARY_PATH` passthrough. The SOP stage reuses the persistent Ollama service already running on HPC (endpoint discovery file pattern from `3-analyze/hpc/`).

## Acceptance criteria

- [ ] `11-sop/hpc/build-sif.sh` converts the Docker image to `sop.sif` and writes it to the scratch SIF path alongside `whisper-hpc.sif`
- [ ] `11-sop/hpc/submit-sop.sh` is a SLURM array job that maps `SLURM_ARRAY_TASK_ID` to a pending transcript, reads the Ollama endpoint from the scratch discovery file, and calls `sop.py` inside the Singularity container
- [ ] `submit-sop.sh` uses `SLURM_SUBMIT_DIR` to derive `PROJECT_ROOT` and binds it as `/workspace`
- [ ] `submit-sop.sh` uses the `singularity exec ... bash -c "export LD_LIBRARY_PATH=...; python ..."` wrapper pattern
- [ ] `submit-sop.sh` fails with a clear error if the Ollama endpoint discovery file does not exist
- [ ] `submit-sop.sh` logs per-task stdout/stderr to `logs/%A_%a.out` following the existing convention
- [ ] `11-sop/hpc/run-sop.sh` is an interactive `srun` wrapper that takes a transcript path as its only positional argument and reads the Ollama endpoint from the discovery file
- [ ] A HPC pipeline config (`pipeline.hpc.yaml` or documented env override) sets `max_transcript_words: 0` and `sop.model: qwen2.5:14b` (or larger)
- [ ] `11-sop/hpc/README.md` documents the end-to-end HPC workflow: build SIF → ensure Ollama service is running → submit array job

## Blocked by

- Blocked by `issues/todo/072-sop-docker-packaging.md`

## User stories addressed

- User story 16
- User story 17
- User story 18
