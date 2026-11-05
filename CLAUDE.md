# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

SLICK+ HPC Demo — end-to-end multilingual video processing pipeline: fine-tunes `openai/whisper-small` on Google FLEURS across five languages (en, es, fr, zh-CN, ar) using a SLURM job array, then orchestrates inference → analysis → sentiment → embedding/search → SOP generation. Demonstrates speech transcription training at HPC scale plus a full post-processing pipeline for learning-content production.

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
python 2-inference/infer.py --model_dir checkpoints/es --audio path/to/audio.wav
# Add --segments to write transcript.txt and timestamped segments.json into the same directory as the audio file
```

**Run the full post-processing pipeline:**
```bash
python pipeline.py --lang en
python pipeline.py --file inbox/en/foo.mp3   # single file (also used as HPC array task)
```

## Architecture

| File | Role |
|---|---|
| `1-train/train.py` | Full training pipeline: loads FLEURS, preprocesses audio to mel features, fine-tunes Whisper via `Seq2SeqTrainer`, reports WER per epoch |
| `1-train/submit-gpu.sh` | SLURM job array definition — maps array index 0–4 to language codes, allocates 1 GPU per task |
| `1-train/submit-cpu.sh` | SLURM job array definition — CPU-only fallback variant |
| `2-inference/infer.py` | **Primary inference module.** Standalone CLI and pipeline import. Exports `transcribe()` → plain string and `transcribe_with_segments()` → `(text, segments)` tuple for downstream embedding. `--segments` flag writes `transcript.txt` and timestamped `segments.json` into the same directory as the audio file. |
| `2-inference/infer-30-secs.py` | Single 30-second window variant — uses `WhisperProcessor`/`WhisperForConditionalGeneration` directly (no chunking); limited to ≤30 s audio; exports `transcribe()` → plain string. |
| `2-inference/infer-full.py` | Chunked-pipeline variant — uses HuggingFace `pipeline` with `chunk_length_s=30, stride_length_s=5`; supports any-length audio; exports `transcribe()` → plain string. |
| `3-analyze/analyze.py` | LLM feature extraction via Ollama — sends transcript to Llama and returns structured JSON with `title`, `description`, `tags`, `goals`, and `skills`. |
| `4-file-sync/sync.sh` | rclone-based cloud↔HPC file transfer: syncs a configured Google Drive (or any rclone remote) input folder to `sync/input/` and uploads `sync/output/` back. All paths and remote names are set via environment variables. |
| `5-sentiment/sentiment.py` | HuggingFace sentiment classifier — aggregates per-chunk labels to video-level score |
| `6-embed/embed_server.py` | Flask service (port 8765): POST /embed — encodes text with multilingual-e5-large, returns raw vectors (no Qdrant dependency) |
| `7-index/index_server.py` | Flask service (port 8766): POST /index, POST /metadata — receives vectors, writes to Qdrant `video_chunks` / `video_metadata` (no model dependency) |
| `8-search/search.py` | Semantic search over indexed chunks in Qdrant — returns timestamped results |
| `9-graph/graph.py` | Knowledge-graph builder over transcript metadata |
| `9-graph/playlist.py` | Playlist generator from graph traversal |
| `10-agent/agent.py` | LangGraph RAG chat agent over the Qdrant knowledge base. Supports factual Q&A, full transcript retrieval, and playlist generation with a human-approval interrupt gate before writing artefacts. |
| `11-sop/sop.py` | SOP generator: combines transcript + `analysis.json` and calls Ollama to produce a structured `.sop.md` (and `.sop.pdf` via xhtml2pdf). |
| `11-sop/teleprompter.py` | Teleprompter script generator: reads a `.sop.md` and produces a speech-optimised presenter script with an SME review checklist appended. |
| `pipeline.py` | Orchestrator: infer → analyze → sentiment → embed + index → sop. Each stage is independently toggleable via `pipeline.yaml` flags. |

## Local Development

**Start all services (embed, index, Qdrant, Ollama):**
```bash
docker compose up
```

**Run the shell-script test suite (bats):**
```bash
make test          # alias for: bats tests/
```

**Run Python unit tests for individual stages:**
```bash
pytest             # see DEVELOPMENT.md for per-stage flags and coverage options
```

**Key design decisions:**
- One fine-tuned model per language (not multilingual single-model) — jobs run in parallel, each converges independently
- `--max_train_samples` flag in `1-train/train.py` enables fast local smoke tests without a GPU
- Checkpoints saved per epoch; best model (lowest WER) loaded at end of training
- `fp16=True` automatically enabled when a GPU is present
- `pipeline.py` lazy-loads each stage module so missing dependencies only fail at runtime for that stage, not at import time

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

**SIF location:** `whisper-hpc.sif` lives at `/scratch/project_465003359/mcgowank/whisper-hpc.sif` (not inside the project directory).

## Extending

To add a language: add it to `LANGUAGE_CODES` and `COMMON_VOICE_SPLITS` in `1-train/train.py`, add it to the `LANGUAGES` array in the submit scripts, and expand `--array` to match.

To swap in client audio data: replace the `load_fleurs()` call with a custom `datasets.Dataset` — the rest of the pipeline is data-source agnostic.
