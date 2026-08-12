# SLICK+ HPC Demo — Multilingual Whisper Fine-Tuning

Fine-tunes `openai/whisper-small` on [Google FLEURS](https://huggingface.co/datasets/google/fleurs) across five languages simultaneously using a SLURM job array on HPC GPU infrastructure. Demonstrates how multilingual speech model training that would take weeks on standard infrastructure can be reduced to days.

## Languages

| Code | Language | FLEURS locale |
|------|----------|---------------|
| `en` | English | `en_us` |
| `es` | Spanish | `es_419` |
| `fr` | French | `fr_fr` |
| `zh-CN` | Mandarin | `cmn_hans_cn` |
| `ar` | Arabic | `ar_eg` |

## Setup

### Mac (Apple Silicon) — local dev

Run directly in a virtualenv. PyTorch's MPS backend is used automatically; Docker cannot access it.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Linux / CI — CPU-only Docker

```bash
docker compose run dev python train.py --language es --output_dir ./checkpoints/es --max_train_samples 200 --epochs 1
```

### HPC — Singularity (AMD/ROCm)

Pull the image once on the login node (replace `YOUR_ORG`):

```bash
singularity pull ~/whisper-hpc.sif docker://ghcr.io/YOUR_ORG/whisper-hpc:latest
```

Then submit the job array (see [Training](#training) below). The `submit.sh` script invokes the container automatically.

**To build and push a new image** (run locally with Docker installed):

```bash
docker build -t ghcr.io/YOUR_ORG/whisper-hpc:latest .
docker push ghcr.io/YOUR_ORG/whisper-hpc:latest
```

## Training <a name="training"></a>

**Smoke test — single language, small sample, no GPU required:**
```bash
python train.py --language es --output_dir ./checkpoints/es --max_train_samples 200 --epochs 1 --batch_size 2
```

**Full HPC run — all 5 languages in parallel:**
```bash
mkdir -p logs
sbatch submit.sh
```

Each language runs as an independent SLURM job (one GPU each). Monitor progress:
```bash
squeue -u $USER
tail -f logs/<jobid>_<arrayindex>.out
```

Checkpoints are saved per epoch to `checkpoints/<lang>/`. The best checkpoint (lowest WER) is restored automatically at the end of training.

## Inference

```bash
python infer.py --model_dir checkpoints/es --audio path/to/audio.wav
python infer.py --model_dir checkpoints/fr --audio path/to/audio.mp3 --language french
```

Audio of any length is supported — the pipeline chunks into overlapping 30-second windows automatically.

## How it works

Whisper is an encoder-decoder transformer pretrained by OpenAI on 680,000 hours of multilingual audio. Fine-tuning adapts it to the acoustic style of a specific domain (in this case, FLEURS read speech) without training from scratch.

Each training job:
1. Converts audio to 80-channel log-mel spectrograms
2. Tokenizes transcriptions into Whisper's BPE vocabulary
3. Fine-tunes all model weights via cross-entropy loss with teacher forcing
4. Evaluates Word Error Rate (WER) on the validation set each epoch

On HPC, all five jobs run concurrently — wall-clock time equals one language, not five.

## Extending

**Add a language:** add entries to `LANGUAGE_CODES` and `FLEURS_CODES` in `train.py`, add the code to `LANGUAGES` in `submit.sh`, and expand `--array` to match.

**Use client audio data:** replace the `load_fleurs()` call in `train.py` with a custom `datasets.Dataset` — the rest of the pipeline is data-source agnostic.

**Update the container image:** edit `requirements.txt` or the `Dockerfile`, then rebuild and push:
```bash
docker build -t ghcr.io/YOUR_ORG/whisper-hpc:latest .
docker push ghcr.io/YOUR_ORG/whisper-hpc:latest
singularity pull --force ~/whisper-hpc.sif docker://ghcr.io/YOUR_ORG/whisper-hpc:latest
```
