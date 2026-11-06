# 12-tts/local — Run TTS Generation Locally

Converts a teleprompter script (`.teleprompter.md`) to a WAV audio file using Ollama's `lfm3-audio` model via the `/v1/audio/speech` API.

---

## Prerequisites

- Ollama **0.40.11 or later** running locally
- `lfm3-audio` pulled into Ollama
- Python virtual environment activated with `requests` installed

```bash
# Verify Ollama version (must be 0.40.11+)
ollama --version

# Pull the TTS model (2.1 GB, one-time)
ollama pull lfm3-audio

# Activate the venv
source venv/bin/activate
pip install -r 12-tts/requirements.txt
```

---

## Running

```bash
bash 12-tts/local/run.sh results/en/myvideo.teleprompter.md
```

This reads:

- `results/en/myvideo.teleprompter.md`

And writes:

- `results/en/myvideo.teleprompter.wav` — single concatenated WAV (16-bit, mono, 24 kHz)

The script is idempotent — if `.teleprompter.wav` already exists it exits immediately without calling the API.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL` | `lfm3-audio` | Ollama TTS model name |
| `VOICE` | `male` | Voice name passed to the model |
| `OLLAMA_HOST` | `localhost:11434` | Ollama API host |

```bash
MODEL=lfm3-audio VOICE=female bash 12-tts/local/run.sh results/en/myvideo.teleprompter.md
```

---

## Files

| File | Role |
|------|------|
| `run.sh` | Runs `tts.py` for a single teleprompter file |
