# Training — Multilingual Whisper Fine-Tuning

Fine-tunes `openai/whisper-small` on [Google FLEURS](https://huggingface.co/datasets/google/fleurs) across five languages simultaneously using a SLURM job array on HPC GPU infrastructure.

## Languages

| Code | Language | FLEURS locale |
|------|----------|---------------|
| `en` | English | `en_us` |
| `es` | Spanish | `es_419` |
| `fr` | French | `fr_fr` |
| `zh-CN` | Mandarin | `cmn_hans_cn` |
| `ar` | Arabic | `ar_eg` |

## Running

Checkpoints are saved per epoch to `checkpoints/<lang>/`. The best checkpoint (lowest WER) is restored automatically at the end of training.

### Local — native Python

GPU used automatically if present (MPS on Apple Silicon, CUDA on Linux).

```bash
bash 1-train/local/train.sh
```

### Docker — CPU only (Mac Docker Desktop cannot access GPU)

```bash
bash 1-train/docker/train.sh
```

> Requires at least 2 GB of shared memory for DataLoader workers. Set via `shm_size: '2gb'` in `docker-compose.yml`.

### HPC — all 5 languages in parallel (AMD/ROCm GPU)

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

## How it works

Whisper is an encoder-decoder transformer pretrained by OpenAI on 680,000 hours of multilingual audio. Fine-tuning adapts it to the acoustic style of a specific domain (in this case, FLEURS read speech) without training from scratch.

Each training job:
1. Converts audio to 80-channel log-mel spectrograms
2. Tokenizes transcriptions into Whisper's BPE vocabulary
3. Fine-tunes all model weights via cross-entropy loss with teacher forcing
4. Evaluates Word Error Rate (WER) on the validation set each epoch

On HPC, all five jobs run concurrently — wall-clock time equals one language, not five.

## Extending

**Add a language:** add entries to `LANGUAGE_CODES` and `FLEURS_CODES` in `train.py`, add the code to `LANGUAGES` in the submit scripts, and expand `--array` to match.

**Use client audio data:** replace the `load_fleurs()` call in `train.py` with a custom `datasets.Dataset` — the rest of the pipeline is data-source agnostic.

## Monitoring GPU usage on the compute node

SSH into the node running your job and start the GPU monitor in one command:

```bash
ssh $(squeue -u $USER -h -o "%N" | head -1)
```

Once on the node, watch GPU utilisation update every second:

```bash
watch -n 1 rocm-smi
```

## Files

| File | Role |
|------|------|
| `train.py` | Full training pipeline: loads FLEURS, preprocesses audio to mel features, fine-tunes Whisper via `Seq2SeqTrainer`, reports WER per epoch |
| `local/train.sh` | Run training directly with Python (local dev) |
| `docker/train.sh` | Run training via Docker Compose (CPU only) |
| `hpc/train-sbatch-gpu.sh` | SLURM job array — AMD/ROCm GPU nodes, 1 GPU per language |
| `hpc/train-sbatch-cpu.sh` | SLURM job array — CPU-only fallback |
