# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

SLICK+ HPC Demo — fine-tunes `openai/whisper-small` on Google FLEURS across five languages (en, es, fr, zh-CN, ar) simultaneously using a SLURM job array (one GPU job per language). Demonstrates multilingual speech transcription training at HPC scale.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Commands

**Train a single language locally (smoke test):**
```bash
python 1-train/train.py --language es --output_dir ./checkpoints/es --max_train_samples 200 --epochs 1
```

**Submit all 5 languages in parallel on HPC:**
```bash
mkdir -p logs
sbatch 1-train/submit-gpu.sh
```

**Monitor SLURM jobs:**
```bash
squeue -u $USER
tail -f logs/<jobid>_<arrayindex>.out
```

**Transcribe audio with a fine-tuned checkpoint:**
```bash
python infer.py --model_dir checkpoints/es --audio path/to/audio.wav
```

## Architecture

| File | Role |
|---|---|
| `1-train/train.py` | Full training pipeline: loads Common Voice, preprocesses audio to mel features, fine-tunes Whisper via `Seq2SeqTrainer`, reports WER per epoch |
| `1-train/submit-gpu.sh` | SLURM job array definition — maps array index 0–4 to language codes, allocates 1 GPU per task |
| `1-train/submit-cpu.sh` | SLURM job array definition — CPU-only fallback variant |
| `infer.py` | Loads a saved checkpoint and transcribes a local audio file |

**Key design decisions:**
- One fine-tuned model per language (not multilingual single-model) — jobs run in parallel, each converges independently
- `--max_train_samples` flag in `1-train/train.py` enables fast local smoke tests without a GPU
- Checkpoints saved per epoch; best model (lowest WER) loaded at end of training
- `fp16=True` automatically enabled when a GPU is present

## HPC Script Conventions

**`bash -c "..."` wrapper in Singularity calls:** The scripts use `singularity exec ... bash -c "..."` rather than passing the python command directly. This is required so that `export LD_LIBRARY_PATH=...` runs *inside* the container environment and persists for the python process. Without the wrapper, environment variables set before the command would apply on the host, not inside the container, this enables the GPU on HPC sbatch jobs.

**Project root binding:** All Singularity scripts bind the project root as `/workspace`. Because scripts live in subdirectories (`1-train/hpc/`, `2-inference/hpc/`), `$PWD` is wrong when running from inside those directories.

- `sbatch` scripts (`1-train/hpc/`): use `SLURM_SUBMIT_DIR` (set by SLURM to the directory `sbatch` was called from):
  ```bash
  PROJECT_ROOT="$(cd "$SLURM_SUBMIT_DIR/../.." && pwd)"
  ```
- `srun` scripts (`2-inference/hpc/`): use `$PWD` at call time since srun is interactive:
  ```bash
  PROJECT_ROOT="$(cd "$PWD/../.." && pwd)"
  ```

Then bind with `--bind "$PROJECT_ROOT:/workspace"` instead of `--bind "$PWD:/workspace"`.

**SIF location:** `whisper-hpc.sif` lives at `/scratch/project_465003209/mcgowank/whisper-hpc.sif` (not inside the project directory).

## Extending

To add a language: add it to `LANGUAGE_CODES` and `COMMON_VOICE_SPLITS` in `1-train/train.py`, add it to the `LANGUAGES` array in the submit scripts, and expand `--array` to match.

To swap in client audio data: replace the `load_fleurs()` call with a custom `datasets.Dataset` — the rest of the pipeline is data-source agnostic.
