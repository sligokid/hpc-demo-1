# Inference — Whisper Transcription & Translation

Transcribes / Translates audio to text using a fine-tuned language specific Whisper checkpoint. Audio of any length is supported — the pipeline chunks into overlapping 30-second windows automatically.

## Running

### Local — native Python

### Transcription mode
Transcribe audio/video files to text

### Translation mode

Pass `--task translate` to produce an English transcript from non-English audio without retraining:

Run from the `local/` directory:

```bash
cd 2-inference/local
bash infer.sh           # EN transcription
bash infer-translate.sh # ES → EN translation
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

### HPC — Singularity (AMD/ROCm)

Pull the SIF file first: see `../../update-sifs.sh`

Run from the project root:

```bash
./2-inference/hpc/infer-on-gpu.sh           # transcribe (GPU)
./2-inference/hpc/infer-on-cpu.sh           # transcribe (CPU fallback)
./2-inference/hpc/infer-translate-on-gpu.sh # ES → EN translation (GPU)
```

## Tests

Run from the `2-inference/` directory:
```bash
pytest test_infer.py
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
