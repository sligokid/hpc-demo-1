# PRD: Audio Transcription Pipeline

## Problem Statement

Researchers and content producers working with multilingual audio need a way to produce accurate text transcripts from audio files using fine-tuned Whisper checkpoints. The standard Whisper API does not expose fine-tuned checkpoint inference, and the HuggingFace pipeline requires configuration to handle long-form audio, device selection, and task routing (transcribe vs. translate). Without a dedicated inference script, users must write this boilerplate themselves for every audio file they want to transcribe.

## Solution

Two inference scripts — `infer.py` (pipeline-based, recommended) and `infer-full.py` (low-level, for advanced use) — provide a consistent CLI for transcribing audio files of any length using a fine-tuned Whisper checkpoint. Both support multilingual transcription and English translation as a secondary task. Device selection (CUDA, Apple MPS, CPU) is automatic.

## How It Works

Whisper is an encoder-decoder transformer pretrained by OpenAI on 680,000 hours of multilingual audio. Fine-tuning adapts it to the acoustic style of a specific domain without training from scratch.

At inference time:
1. Audio is loaded and resampled to 16 kHz mono via `librosa`.
2. The audio array is passed to the Whisper pipeline, which chunks it into overlapping 30-second windows (chunk_length_s=30, stride_length_s=5) to handle files longer than 30 seconds.
3. The decoder is conditioned on two special tokens: a **language token** and a **task token** (`<|transcribe|>` or `<|translate|>`).
4. The decoder autoregressively generates text tokens, which are decoded back to a string.

### Translation mode

Passing `--task translate` swaps the task token from `<|transcribe|>` to `<|translate|>`, instructing the decoder to produce English output regardless of source language.

**Key constraint:** the five fine-tuned checkpoints in this project were trained exclusively with `task=transcribe`. The translation head (the weights activated by `<|translate|>`) was never updated during fine-tuning — it retains OpenAI's pretrained values. Translation quality therefore reflects `openai/whisper-small`'s pretrained translation capability, which is weaker than its transcription capability, especially for underrepresented languages.

**Translation always outputs English only.** There is no arbitrary source→target language pair support in Whisper's translate task.

## User Stories

1. As a developer, I want to transcribe a local audio file with a one-line CLI command, so that I can produce a transcript without writing Python boilerplate.
2. As a developer, I want audio of any length to be transcribed correctly, so that I am not limited to 30-second clips.
3. As a developer, I want the script to automatically use the best available device (GPU, MPS, or CPU), so that I do not need to configure hardware manually.
4. As a developer, I want to specify a fine-tuned checkpoint directory via `--model_dir`, so that I can switch between language-specific models.
5. As a developer, I want to force the source language via `--language`, so that I can override the model's auto-detection when needed.
6. As a developer, I want to pass `--task translate` to produce an English transcript from non-English audio, so that I can get a rough English translation without retraining.
7. As a developer, I want `--task transcribe` to be the default, so that existing workflows are not broken.
8. As a developer, I want the terminal output to clearly label whether the result is a transcription or a translation, so that I can confirm which mode was active.
9. As a developer, I want to use `.wav`, `.mp3`, and other common audio formats, so that I am not limited to a single file type.
10. As a developer, I want the script to work on Apple Silicon (MPS), Linux CPU, and CUDA GPUs, so that the same code runs locally and on HPC.
11. As a developer working on HPC, I want a Singularity-compatible inference script, so that I can run transcription on AMD/ROCm GPU nodes.

## Implementation Decisions

### Modules

- **`infer.py`** — primary inference script. Uses HuggingFace `pipeline("automatic-speech-recognition")` with `chunk_length_s=30` and `stride_length_s=5` for transparent long-form audio handling. Supports `--task transcribe|translate`. Recommended for all standard use.

- **`infer-full.py`** — low-level inference script. Uses `WhisperProcessor` + `WhisperForConditionalGeneration` directly, giving full control over `forced_decoder_ids` and `generate()` call. Used for advanced scenarios where pipeline abstraction is insufficient.

- **`infer-30-secs.py`** — earlier prototype, limited to 30 seconds. Retained for reference; not recommended for new use.

### Audio handling

- All audio loaded via `librosa.load()` at `sr=16_000`, `mono=True`.
- Resampling and channel mixing happen in librosa before the array is passed to the model.
- `infer.py` delegates chunking to the pipeline (`chunk_length_s=30`, `stride_length_s=5`). `infer-full.py` processes a single 30-second window and is therefore limited to short clips.

### Device selection

Auto-detected in order: CUDA → Apple MPS → CPU. The pipeline expects an integer device index for CUDA (`device=0`) vs a string for MPS (`device="mps"`) — this distinction is handled explicitly.

### Task routing

`generate_kwargs = {"task": task}` is passed into the pipeline. When `--language` is also provided, `generate_kwargs["language"] = language` is added. The `forced_decoder_ids` baked into some checkpoint `generation_config` files may conflict with the runtime task — this produces a harmless FutureWarning at runtime and the runtime kwargs take precedence.

### Supported languages (fine-tuned checkpoints)

| Code | Language | FLEURS locale |
|------|----------|---------------|
| `en` | English | `en_us` |
| `es` | Spanish | `es_419` |
| `fr` | French | `fr_fr` |
| `zh-CN` | Mandarin | `cmn_hans_cn` |
| `ar` | Arabic | `ar_eg` |

## Testing Decisions

- **What makes a good test:** test the externally observable behaviour of `transcribe()` — given a known audio input and task flag, assert the output is a non-empty string and that the correct `generate_kwargs` are constructed. Do not test HuggingFace internals or Whisper model weights.
- **Modules to test:** the `transcribe()` function in `infer.py`, specifically device selection logic and `generate_kwargs` construction for each task/language combination.
- **Approach:** mock `pipeline` and `librosa.load` to avoid loading real weights in unit tests. Integration tests can use a small real checkpoint and a short audio clip.

## Out of Scope

- Fine-tuning models in translation mode (separate workstream; requires paired audio + English reference translations).
- Translation to any language other than English.
- Batch transcription of multiple audio files in a single command.
- Real-time / streaming transcription.
- Quality evaluation (WER, BLEU) of inference output.
- A web API or UI wrapping the inference scripts.
- Improving translation quality (upgrade path: switch to `openai/whisper-large-v3`, or fine-tune in translation mode with FLEURS reference translations).

## Further Notes

- Mixed-language output in translation mode (model partially reverts to source language mid-sequence) is a known failure mode of `whisper-small`. It is more common with languages underrepresented in Whisper's pretraining data.
- The `forced_decoder_ids` conflict warning printed at runtime is harmless: the checkpoint's baked-in `generation_config` sets `forced_decoder_ids` for transcription mode, but passing `task=translate` via `generate_kwargs` overrides it correctly.
- On HPC (AMD/ROCm), inference is run via Singularity using `infer-on-gpu.sh` and `infer-translate-on-gpu.sh` wrapper scripts.
