## Parent PRD

`issues/prd.md`

## What to build

HPC deployment for `12-tts`: three SLURM scripts that run `tts.py` via Singularity on LUMI, following the exact pattern of `11-sop/hpc/`.

- `12-tts/hpc/tts-sbatch.sh` — SLURM array task; reads a manifest file, derives the teleprompter file path for each array index, runs `tts.py` inside `singularity exec` with a `bash -c` wrapper for `LD_LIBRARY_PATH`; binds project root as `/workspace` using `SLURM_SUBMIT_DIR`; reads Ollama endpoint from `$SCRATCH/ollama.endpoint`; SIF at `/scratch/project_465003359/mcgowank/tts-tools.sif`
- `12-tts/hpc/tts-hpc-submit.sh` — scans `sync/input/*/` for `*.teleprompter.md` files whose `*.teleprompter.wav` does not yet exist in `sync/output/`; writes a timestamped manifest to `logs/`; submits a SLURM array job via `tts-sbatch.sh`
- `12-tts/hpc/tts-hpc-poll.sh` — SLURM job that calls `tts-hpc-submit.sh` then reschedules itself every 10 minutes via a trap on EXIT; job name `H-tts`; stoppable with `scancel --name=H-tts --user=$USER`

SLURM account: `project_465003359`, partition: `small`.

> **Model:** Uses `lfm3-audio` (not `phonon`). `phonon` requires Apple Silicon MLX and cannot run on HPC (linux/x86_64). `lfm3-audio` is linux-compatible, 2.1 GB, and uses the same `/v1/audio/speech` API.
>
> **Ollama version requirement:** The `/v1/audio/speech` endpoint requires Ollama **0.40.11 or later** running on the HPC Ollama node. Verify with `cat $SCRATCH/ollama.endpoint | xargs -I{} curl -s http://{}/api/version` before submitting jobs. Pull `lfm3-audio` into the HPC Ollama instance before the first job runs.
>
> **SIF requirement:** `tts-tools.sif` is managed via `update-sifs.sh` at the project root. Run it on HPC to pull `sligokid/tts-tools:latest` from Docker Hub into `/scratch/project_465003359/mcgowank/tts-tools.sif`. The existing `sop-tools.sif` does not include `tts.py` and cannot be reused.

## Acceptance criteria

- [ ] Ollama on HPC is version 0.40.11+ (verified before submitting)
- [ ] `lfm3-audio` model is pulled into the HPC Ollama instance
- [ ] `tts-tools.sif` built and placed at `/scratch/project_465003359/mcgowank/tts-tools.sif` via `update-sifs.sh`

- [ ] `tts-sbatch.sh` runs `tts.py` via `singularity exec … bash -c "…"` with correct `/workspace` binding
- [ ] `tts-sbatch.sh` reads `OLLAMA_HOST` from `$SCRATCH/ollama.endpoint` and exits with error if file is missing
- [ ] `tts-sbatch.sh` handles array overrun (exits cleanly if task index >= manifest length)
- [ ] `tts-hpc-submit.sh` correctly identifies pending files (teleprompter.md exists, teleprompter.wav does not)
- [ ] `tts-hpc-submit.sh` writes manifest with paths relative to project root (for `/workspace` mapping)
- [ ] `tts-hpc-submit.sh` exits cleanly with a message if no pending files are found
- [ ] `tts-hpc-poll.sh` reschedules itself via EXIT trap regardless of success or failure
- [ ] `tts-hpc-poll.sh` job name is `H-tts`; `scancel --name=H-tts` stops the loop

## Blocked by

- `issues/tts/075-tts-core.md`

## User stories addressed

- User story 11
- User story 12
- User story 13
- User story 14
- User story 17
