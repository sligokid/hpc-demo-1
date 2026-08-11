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
python train.py --language es --output_dir ./checkpoints/es --max_train_samples 200 --epochs 1
```

**Submit all 5 languages in parallel on HPC:**
```bash
mkdir -p logs
sbatch submit.sh
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
| `train.py` | Full training pipeline: loads Common Voice, preprocesses audio to mel features, fine-tunes Whisper via `Seq2SeqTrainer`, reports WER per epoch |
| `submit.sh` | SLURM job array definition — maps array index 0–4 to language codes, allocates 1 GPU per task |
| `infer.py` | Loads a saved checkpoint and transcribes a local audio file |

**Key design decisions:**
- One fine-tuned model per language (not multilingual single-model) — jobs run in parallel, each converges independently
- `--max_train_samples` flag in `train.py` enables fast local smoke tests without a GPU
- Checkpoints saved per epoch; best model (lowest WER) loaded at end of training
- `fp16=True` automatically enabled when a GPU is present

## Extending

To add a language: add it to `LANGUAGE_CODES` and `COMMON_VOICE_SPLITS` in `train.py`, add it to the `LANGUAGES` array in `submit.sh`, and expand `--array` to match.

To swap in client audio data: replace the `load_fleurs()` call with a custom `datasets.Dataset` — the rest of the pipeline is data-source agnostic.
