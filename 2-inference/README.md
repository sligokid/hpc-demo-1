# Inference — Whisper Transcription & Translation

Transcribes / Translates audio to text using a fine-tuned language-specific Whisper checkpoint. Audio of any length is supported — the pipeline chunks into overlapping 30-second windows automatically.

---

## Models Used

| Model | Source | Role |
|-------|--------|------|
| `openai/whisper-small` (fine-tuned) | Local checkpoint in `checkpoints/<lang>/` | Primary transcription model — fine-tuned per language by `1-train` |
| `openai/whisper-small` (pretrained) | [HuggingFace](https://huggingface.co/openai/whisper-small) | Fallback if no fine-tuned checkpoint exists; also used for translation via pretrained translation head |

---

## How it Works

`infer.py` uses the HuggingFace `pipeline` API with `task="automatic-speech-recognition"` and `chunk_length_s=30`. This splits any-length audio into overlapping 30-second windows, runs each through the Whisper encoder-decoder, then stitches the results back together.

1. **Load checkpoint** — looks for a fine-tuned checkpoint in `checkpoints/<lang>/`. Falls back to `openai/whisper-small` from HuggingFace if none exists.
2. **Chunk audio** — splits into 30-second windows with a 5-second stride overlap to prevent word loss at boundaries.
3. **Transcribe** — each chunk is converted to an 80-channel log-mel spectrogram, passed through the Whisper encoder, then decoded autoregressively with the language forced via `forced_decoder_ids`.
4. **Stitch** — chunk transcripts are concatenated. Timestamps from each chunk are offset and merged into a single segment list.
5. **Write outputs** — `.transcript.txt` (plain text) and `.segments.json` (timestamped segments) are written to `sync/output/<lang>/`.

**Device selection:** CUDA → Apple Silicon MPS → CPU, chosen automatically at load time.

---

## Sample Output

`infer.py` writes two files per audio file:

**`sync/output/en/my-video.transcript.txt`** — plain text transcript:
```
and now i'd like to show you how to create a slick we've made this
process as simple as possible so let's get started first click the
create button in the top right corner of the screen...
```

**`sync/output/en/my-video.segments.json`** — timestamped segments:
```json
[
  {"start": 0.0,  "end": 4.2,  "text": "and now i'd like to show you how to create a slick"},
  {"start": 4.2,  "end": 8.7,  "text": "we've made this process as simple as possible so let's get started"},
  {"start": 8.7,  "end": 13.1, "text": "first click the create button in the top right corner of the screen"}
]
```

The segments JSON is consumed directly by `3-analyze`, `5-sentiment`, and `6-embed` in the pipeline.

---

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

---

## Running locally

```bash
cd 2-inference/local
bash infer.sh           # EN transcription
bash infer-translate.sh # ES → EN translation
```

**Translation constraints:**
- Translation always outputs **English** — Whisper's translate task is English-output only.
- The fine-tuned checkpoints were trained with `task="transcribe"`. Translation uses Whisper's pretrained translation head — quality is generally weaker than transcription.
- `--language` can be passed alongside `--task translate` to force the source language.

---

## Docker

CPU only — Mac Docker Desktop cannot access GPU.

```bash
cd 2-inference/docker
bash infer.sh
```

---

## Running on LUMI (HPC)

Pull the SIF file first: see `../../update-sifs.sh`

```bash
./2-inference/hpc/infer-on-gpu.sh           # transcribe (GPU)
./2-inference/hpc/infer-on-cpu.sh           # transcribe (CPU fallback)
./2-inference/hpc/infer-translate-on-gpu.sh # ES → EN translation (GPU)
```
