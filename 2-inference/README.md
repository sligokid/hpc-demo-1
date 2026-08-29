# Inference — Whisper Transcription & Translation

Transcribes audio using a fine-tuned Whisper checkpoint. Audio of any length is supported — the pipeline chunks into overlapping 30-second windows automatically.

## Running

### Local — native Python

Run from the `local/` directory:

```bash
cd 2-inference/local
bash infer.sh           # EN transcription
bash infer-translate.sh # ES → EN translation
```

Or directly from the project root:

```bash
python 2-inference/infer.py --model_dir checkpoints/en --audio 2-inference/audio/sligo-triathlon-club-inviting-women-to-try-a-tri.mp3
python 2-inference/infer.py --model_dir checkpoints/es --audio 2-inference/audio/spanish-telephone-phrases.mp3
```

### Translation mode

Pass `--task translate` to produce an English transcript from non-English audio without retraining:

```bash
python 2-inference/infer.py --model_dir checkpoints/es --audio 2-inference/audio/spanish-telephone-phrases.mp3 --task translate
```

**Constraints:**
- Translation always outputs **English** — Whisper's translate task is English-output only.
- The fine-tuned checkpoints were trained with `task="transcribe"`. Translation uses Whisper's pretrained translation head, not fine-tuned weights. Quality will vary and is generally weaker than transcription.
- `--language` can be passed alongside `--task translate` to force the source language.

### Docker — CPU only (Mac Docker Desktop cannot access GPU)

Run from the `docker/` directory:

```bash
cd 2-inference/docker
bash infer.sh
```

Or directly from the project root:

```bash
docker compose run dev python 2-inference/infer-30-secs.py --model_dir checkpoints/en --audio 2-inference/audio/sligo-triathlon-club-inviting-women-to-try-a-tri.mp3
```

### HPC — Singularity (AMD/ROCm)

Run from the project root:

```bash
./2-inference/hpc/infer-on-gpu.sh           # transcribe (GPU)
./2-inference/hpc/infer-on-cpu.sh           # transcribe (CPU fallback)
./2-inference/hpc/infer-translate-on-gpu.sh # ES → EN translation (GPU)
```

## Tests

```bash
pytest 2-inference/test_infer.py
```

## Files

| File | Role |
|------|------|
| `infer.py` | Transcription using HuggingFace `pipeline` (chunked, any length) |
| `infer-full.py` | Alternate transcription implementation using `WhisperProcessor` directly |
| `infer-30-secs.py` | Single 30-second window variant (no chunking) |
| `local/infer.sh` | Run EN transcription locally with native Python |
| `local/infer-translate.sh` | Run ES→EN translation locally with native Python |
| `docker/infer.sh` | Run transcription via Docker Compose (CPU only) |
| `hpc/infer-on-gpu.sh` | Interactive `srun` job — transcription on AMD/ROCm GPU |
| `hpc/infer-on-cpu.sh` | Interactive `srun` job — transcription on CPU |
| `hpc/infer-translate-on-gpu.sh` | Interactive `srun` job — ES→EN translation on GPU |
| `audio/` | Sample audio files for testing |
| `test_infer.py` | Unit tests for `transcribe()` (mocked, no model weights needed) |
