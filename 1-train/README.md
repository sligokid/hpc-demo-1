# Training — Multilingual Whisper Fine-Tuning

Fine-tunes `openai/whisper-small` on Google FLEURS across five languages simultaneously using a SLURM job array — one GPU job per language.

---

## Models Used

| Model | Source | Role |
|-------|--------|------|
| `openai/whisper-small` | [HuggingFace](https://huggingface.co/openai/whisper-small) | Base model — fine-tuned on FLEURS per language |
| `google/fleurs` | [HuggingFace Datasets](https://huggingface.co/datasets/google/fleurs) | Training and validation data |

---

## How it Works

Whisper is an encoder-decoder transformer pretrained by OpenAI on 680,000 hours of multilingual audio. Fine-tuning adapts it to the acoustic style of a specific domain (FLEURS read speech) without training from scratch.

Each training job:

1. Converts audio to 80-channel log-mel spectrograms
2. Tokenizes transcriptions into Whisper's BPE vocabulary
3. Fine-tunes all model weights via cross-entropy loss with teacher forcing
4. Evaluates Word Error Rate (WER) on the validation set each epoch

Checkpoints are saved per epoch to `checkpoints/<lang>/`. The best checkpoint (lowest WER) is restored automatically at the end of training. On HPC, all five jobs run concurrently — wall-clock time equals one language, not five.

---

## Sample Output

Training logs one line per epoch per language:

```
[es] Epoch 1/3 — loss: 0.4821  WER: 18.34%
[es] Epoch 2/3 — loss: 0.3107  WER: 12.71%
[es] Epoch 3/3 — loss: 0.2543  WER:  9.88%
[es] Best checkpoint (epoch 3, WER 9.88%) saved to checkpoints/es/
```

On HPC, one log file per language under `logs/<jobid>_<arrayindex>.out`:

```
logs/
  12345678_0.out   # en
  12345678_1.out   # es
  12345678_2.out   # fr
  12345678_3.out   # zh-CN
  12345678_4.out   # ar
```

Checkpoints written to `checkpoints/<lang>/` are loaded by `2-inference`.

---

## Files

| File | Role |
|------|------|
| `train.py` | Full training pipeline: loads FLEURS, preprocesses audio to mel features, fine-tunes Whisper via `Seq2SeqTrainer`, reports WER per epoch |
| `local/train.sh` | Run training directly with Python (local dev) |
| `docker/train.sh` | Run training via Docker Compose (CPU only) |
| `hpc/train-sbatch-gpu.sh` | SLURM job array — AMD/ROCm GPU nodes, 1 GPU per language |
| `hpc/train-sbatch-cpu.sh` | SLURM job array — CPU-only fallback |

---

## Languages

| Code | Language | FLEURS locale |
|------|----------|---------------|
| `en` | English | `en_us` |
| `es` | Spanish | `es_419` |
| `fr` | French | `fr_fr` |
| `zh-CN` | Mandarin | `cmn_hans_cn` |
| `ar` | Arabic | `ar_eg` |

---

## Running locally

GPU used automatically if present (MPS on Apple Silicon, CUDA on Linux).

```bash
bash 1-train/local/train.sh
```

---

## Docker

CPU only — Mac Docker Desktop cannot access GPU.

```bash
bash 1-train/docker/train.sh
```

> Requires at least 2 GB of shared memory for DataLoader workers. Set via `shm_size: '2gb'` in `docker-compose.yml`.

---

## Running on LUMI (HPC)

All 5 languages in parallel on AMD/ROCm GPU nodes:

```bash
mkdir -p logs
sbatch 1-train/hpc/train-sbatch-gpu.sh
```

CPU fallback:

```bash
sbatch 1-train/hpc/train-sbatch-cpu.sh
```

Each language runs as an independent SLURM job (one GPU each). Monitor progress:

```bash
squeue -u $USER
tail -f logs/<jobid>_<arrayindex>.out
```

### Monitoring GPU usage

SSH into the node running your job:

```bash
ssh $(squeue -u $USER -h -o "%N" | head -1)
```

Watch GPU utilisation:

```bash
watch -n 1 rocm-smi
```

---

## Extending

**Add a language:** add entries to `LANGUAGE_CODES` and `FLEURS_CODES` in `train.py`, add the code to `LANGUAGES` in the submit scripts, and expand `--array` to match.

**Use client audio data:** replace the `load_fleurs()` call in `train.py` with a custom `datasets.Dataset` — the rest of the pipeline is data-source agnostic.
