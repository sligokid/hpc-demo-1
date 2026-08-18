# PRD: Multilingual Whisper Fine-Tuning on HPC

## Problem Statement

Training a speech recognition model from scratch for multiple languages is prohibitively expensive and slow. OpenAI's Whisper is a strong pretrained multilingual ASR model, but its out-of-the-box performance on domain-specific audio can be improved significantly with fine-tuning. Running five sequential fine-tuning jobs on a single machine would take days; researchers need a way to train all five language models simultaneously on GPU hardware without managing job scheduling manually.

## Solution

Fine-tune `openai/whisper-small` independently on five languages (English, Spanish, French, Mandarin, Arabic) using Google FLEURS as the training dataset. All five training jobs run in parallel on HPC GPU infrastructure via a SLURM job array — one GPU job per language. Each job produces a self-contained checkpoint directory that can be used directly for inference. Wall-clock time equals one language, not five.

## Pipeline Position

```
Google FLEURS dataset  ──►  train.py (one job per language)  ──►  checkpoints/<lang>/
                                                                          │
                                                                          ▼
                                                                      infer.py
```

## How It Works

### Model

`openai/whisper-small` is an encoder-decoder transformer with ~244M parameters, pretrained by OpenAI on 680,000 hours of multilingual audio. Fine-tuning adapts all model weights to the acoustic distribution of FLEURS read speech via cross-entropy loss, without training from scratch.

### Data pipeline (per job)

1. Load the FLEURS split for the target language from HuggingFace Hub.
2. Strip all columns except `audio` and `transcription`; cast audio to 16 kHz mono.
3. Map each example through `prepare_dataset()`:
   - Convert raw audio array to an 80-channel log-mel spectrogram (`WhisperProcessor.feature_extractor`).
   - Tokenize the reference transcription into Whisper's BPE vocabulary (`WhisperProcessor.tokenizer`).
4. Batch examples with `DataCollatorSpeechSeq2SeqWithPadding`, which:
   - Pads input features to a fixed length.
   - Pads and masks labels, replacing padding token IDs with `-100` so they are ignored by the loss.
   - Strips the BOS token from labels if present (Whisper's decoder generates it internally).

### Training loop

`Seq2SeqTrainer` manages the training loop with the following configuration:

| Parameter | Value |
|---|---|
| Base model | `openai/whisper-small` |
| Dataset | Google FLEURS (train/validation splits) |
| Epochs | 3 (default) |
| Batch size per device | 16 (GPU), 2 (local smoke test) |
| Gradient accumulation steps | 2 |
| Learning rate | 1e-5 |
| Warmup steps | 100 |
| Precision | bf16 on CUDA, fp32 otherwise |
| Evaluation strategy | per epoch |
| Checkpoint strategy | per epoch |
| Best model selection | lowest WER on validation set |
| Max generation length | 225 tokens |

### Evaluation metric

Word Error Rate (WER) is computed on the validation set at the end of each epoch. The checkpoint with the lowest WER is restored automatically at the end of training (`load_best_model_at_end=True`).

### HPC execution

Each language is submitted as an independent SLURM array task (`--array=0-4`). The array index maps to a language code (`en`, `es`, `fr`, `zh-CN`, `ar`). Each task requests:
- 1 GPU (`--gres=gpu:1`)
- 4 CPUs (`--cpus-per-task=4`)
- 64 GB RAM
- 8-hour wall-clock limit

Training runs inside a Singularity container (`whisper-hpc.sif`) converted from a Docker image, with `--rocm` for AMD GPU support. A shared HuggingFace dataset cache (`/scratch/.../hf_cache`) is bind-mounted to avoid re-downloading FLEURS for each of the five jobs.

## User Stories

1. As a researcher, I want to fine-tune Whisper on five languages simultaneously, so that total wall-clock time equals one language job rather than five sequential jobs.
2. As a researcher, I want each language to train independently, so that a failure in one job does not affect the others.
3. As a developer, I want to run a fast local smoke test with `--max_train_samples`, so that I can verify the pipeline is correct without a GPU or a full dataset.
4. As a developer, I want device selection (CUDA, MPS, CPU) to be automatic, so that the same script runs locally on Apple Silicon and on HPC GPU nodes.
5. As a developer, I want the best checkpoint (lowest WER) to be restored automatically at the end of training, so that I don't need to manually select among epoch checkpoints.
6. As a researcher, I want WER reported at the end of each epoch on the validation set, so that I can monitor convergence and detect overfitting.
7. As a developer, I want to configure epochs, batch size, and learning rate via CLI flags, so that I can tune hyperparameters without editing the source file.
8. As a developer, I want checkpoints saved per epoch, so that I can resume from a checkpoint if a job is interrupted.
9. As a developer, I want the FLEURS dataset cache shared across all five SLURM tasks, so that each job does not independently re-download the full dataset.
10. As an HPC operator, I want training to run inside a Singularity container, so that the software environment is reproducible and portable across cluster nodes.
11. As a developer, I want to add a new language by editing two files (`train.py` and the SLURM submit script), so that extending the pipeline is straightforward.
12. As a developer, I want to swap in client audio data by replacing the dataset loading function, so that the training pipeline is not tied to FLEURS.
13. As a developer, I want job logs written per task to `logs/<jobid>_<arrayindex>.out`, so that I can tail the output of individual language jobs without interference.
14. As a developer, I want the processor and model saved together to the checkpoint directory, so that inference requires only the checkpoint path and no additional configuration.

## Implementation Decisions

### Modules

- **`train.py`** — full training pipeline. Loads FLEURS, preprocesses audio to mel features, fine-tunes Whisper via `Seq2SeqTrainer`, evaluates WER per epoch, saves best checkpoint. Parameterised by `--language`, `--output_dir`, `--epochs`, `--batch_size`, `--learning_rate`, `--max_train_samples`.

- **`submit-gpu.sh`** — SLURM job array definition for AMD/ROCm GPU nodes. Maps array index 0–4 to language codes, allocates 1 GPU per task, runs training inside Singularity with `--rocm`.

- **`submit-cpu.sh`** — SLURM job array definition for CPU-only runs (testing/fallback). Same structure as the GPU script without GPU allocation.

### Key architectural decisions

- **One model per language, not one multilingual model** — each job fine-tunes an independent checkpoint. Jobs run in parallel and converge independently; there is no cross-language parameter sharing. This maximises per-language accuracy and simplifies failure isolation.
- **`Seq2SeqTrainer` with `predict_with_generate=True`** — evaluation uses full autoregressive generation rather than teacher-forced logits, producing realistic WER values that reflect actual inference behaviour.
- **BOS token stripped from labels in the data collator** — Whisper's decoder generates the BOS token internally; including it in the labels would cause the model to try to predict a token it always produces unconditionally, inflating loss.
- **`forced_decoder_ids=None` in `generation_config`** — clears any baked-in language/task constraints from the pretrained checkpoint so that training can set them explicitly via the processor.
- **`--max_train_samples` flag** — caps the training set size for local smoke tests. Does not affect validation set. Allows full pipeline verification on a laptop in minutes.
- **Shared HF cache** — all five SLURM tasks bind-mount the same `hf_cache` directory. FLEURS is downloaded once; subsequent jobs read from cache. Saves significant I/O time on the login node.
- **`bf16=use_cuda`** — bfloat16 training enabled only on CUDA (AMD ROCm supports bf16). MPS and CPU fall back to fp32.
- **`gradient_checkpointing=False`** — disabled because Whisper's encoder uses convolutional layers incompatible with gradient checkpointing in this configuration.
- **`dataloader_num_workers=4`** — parallelises data loading to avoid GPU starvation during feature extraction.

### Checkpoint layout

```
checkpoints/
├── en/      ← processor + model weights (best WER epoch)
├── es/
├── fr/
├── zh-CN/
└── ar/
```

Each directory contains the full HuggingFace model and processor artifacts, loadable directly by `infer.py` via `--model_dir`.

### Extending the pipeline

- **Add a language:** add entries to `LANGUAGE_CODES` and `FLEURS_CODES` in `train.py`; add the code to `LANGUAGES` in the submit scripts; expand `--array` to match.
- **Use client audio data:** replace the `load_fleurs()` call with a custom `datasets.Dataset` — the rest of the pipeline (preprocessing, collation, training loop) is data-source agnostic.
- **Improve translation quality:** change `task="transcribe"` to `task="translate"` in the processor and `generation_config`, provide paired audio + English reference translations (FLEURS includes these), and use a separate output directory.
- **Scale model size:** change `MODEL_ID` from `openai/whisper-small` to `openai/whisper-medium` or `openai/whisper-large-v3` — no other changes required.

## Testing Decisions

- **What makes a good test:** test the externally observable behaviour of each function — given a mock dataset batch, assert that `prepare_dataset()` returns the correct keys and shapes; given mock predictions, assert that `compute_metrics_fn()` returns the correct WER value. Do not test HuggingFace Trainer internals or model weights.
- **Modules to test:**
  - `prepare_dataset()` — assert `input_features` shape is `(80, 3000)` and `labels` is a non-empty list of integers.
  - `DataCollatorSpeechSeq2SeqWithPadding` — assert batched output has `input_features` and `labels` tensors of correct shape; assert padding positions in labels are `-100`; assert BOS token is stripped.
  - `compute_metrics_fn()` — mock `evaluate.load("wer")`; assert WER is computed from decoded strings and rounded to 4 decimal places.
- **Smoke test (integration):** `python train.py --language es --output_dir /tmp/test-es --max_train_samples 10 --epochs 1` — assert it completes without error and writes a checkpoint directory.

## Out of Scope

- Multi-GPU or distributed training within a single job (each job uses one GPU).
- Mixed-language or multilingual single-model training.
- Hyperparameter search / sweeps.
- Training in translation mode (fine-tuning the translation head).
- Evaluation beyond WER (e.g. CER, BLEU).
- Automatic push to HuggingFace Hub (`push_to_hub=False`).
- Training on languages not in `LANGUAGE_CODES` without code changes.
- Resuming from an interrupted epoch mid-batch (only full-epoch checkpoints are saved).

## Further Notes

- Wall-clock time on the HPC cluster (AMD MI250X GPU, `small-g` partition) is approximately 2–4 hours per language for 3 epochs on the full FLEURS training split, within the 8-hour SLURM time limit.
- The `FutureWarning` about `forced_decoder_ids` seen at inference time originates from the pretrained checkpoint's `generation_config`. It is harmless and does not affect training.
- FLEURS read speech is relatively clean and well-aligned. Fine-tuning on noisier client audio (telephone calls, meeting recordings) will require more epochs and potentially data augmentation.
- `gradient_accumulation_steps=2` with `per_device_train_batch_size=16` gives an effective batch size of 32, which is a reasonable default for `whisper-small` fine-tuning.
