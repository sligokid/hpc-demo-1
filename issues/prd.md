# PRD: Translation Mode for Whisper Inference

## Problem Statement

Users running inference with fine-tuned Whisper checkpoints currently can only transcribe audio into the same language it was spoken in. There is no way to produce an English transcript from, say, Spanish or Arabic audio using the existing `infer.py` interface. Whisper's pretrained weights already support cross-lingual translation to English, but this capability is not exposed in the current tooling.

## Solution

Add a `--task` flag to `infer.py` that allows the user to choose between `transcribe` (default, current behaviour) and `translate` (output English text regardless of input language). No retraining is required — Whisper's pretrained translation capability is used as-is through the existing `generate()` call. The README is updated to document this capability and its constraints.

## User Stories

1. As a developer, I want to pass `--task translate` to `infer.py` so that I can get an English transcript from a Spanish audio file without retraining any model.
2. As a developer, I want `--task transcribe` to remain the default so that existing scripts and workflows are not broken.
3. As a developer, I want the `--task` flag to work with any of the five fine-tuned language checkpoints (en, es, fr, zh-CN, ar) so that I can test translation across all supported languages.
4. As a developer, I want the output label in the terminal to reflect the active task (e.g. "Transcription:" vs "Translation:") so that I can immediately see which mode was used.
5. As a developer, I want the README to explain that translation always outputs English so that I do not mistakenly expect arbitrary target-language output.
6. As a developer, I want the README to note that translation quality reflects Whisper's pretrained weights (not fine-tuned translation) so that I have accurate expectations about output quality.
7. As a developer, I want the README to show a concrete example command for translation so that I can use it without reading the source code.
8. As a developer, I want the `--language` flag to continue working alongside `--task translate` so that I can explicitly force the source language when needed.
9. As a developer, I want the interface change to be backward-compatible so that any existing call to `infer.py` without `--task` continues to work identically.
10. As a future developer, I want a note in the codebase indicating that fine-tuning in translation mode is a known extension point so that the path to higher-quality translation is clearly signposted.

## Implementation Decisions

### Modules to modify

- **Inference script** — add a `--task` argument (`choices=["transcribe", "translate"]`, default `"transcribe"`). Pass the value into the `get_decoder_prompt_ids()` call (which already accepts a `task` parameter) and use it when no `forced_decoder_ids` override is needed. Update the terminal output label to reflect the active task.

- **README** — add a dedicated subsection under Inference covering:
  - The `--task translate` flag and an example command
  - The constraint that translation always outputs English (Whisper's translate task is English-only)
  - A note that quality reflects Whisper's pretrained translation weights, not fine-tuned translation
  - A forward reference indicating that fine-tuning in translation mode is a possible future extension

### Key constraints

- Whisper's `translate` task always produces **English output**, regardless of source language. There is no arbitrary source→target translation.
- The five fine-tuned checkpoints were trained with `task="transcribe"`. Using them for `task="translate"` leverages the pretrained head, not fine-tuned translation weights. Quality will vary by language.
- No changes to `train.py`, `submit.sh`, or any Docker/Singularity artefacts are required.

### Interface

```
python infer.py --model_dir checkpoints/es --audio path/to/audio.wav --task translate
```

## Testing Decisions

- **What makes a good test:** test the externally observable behaviour of the inference function — given a known audio input and a task flag, assert that the output is a non-empty string and that the correct `forced_decoder_ids` (or `None`) are passed to `generate()`. Do not test internal Whisper model weights or HuggingFace internals.
- **Module to test:** the `transcribe()` function in the inference script, specifically the branching logic that sets `forced_decoder_ids` based on the `task` argument.
- **Approach:** mock `WhisperForConditionalGeneration` and `WhisperProcessor` to avoid loading real model weights in tests. Assert that `get_decoder_prompt_ids()` is called with `task="translate"` when the flag is set, and with `task="transcribe"` (or the default) otherwise.
- **No tests required** for the README changes.

## Out of Scope

- Fine-tuning models in `task="translate"` mode (paired audio + English translation labels, separate training run).
- Translation into any language other than English — Whisper's translate task is English-output only.
- Batch translation of multiple audio files in a single command.
- Quality evaluation (BLEU score) of translation output.
- Any changes to the SLURM job array or container images.

## Further Notes

- If fine-tuned translation quality becomes a requirement in future, the extension point is `train.py`: change `task="transcribe"` to `task="translate"` in the processor and `generation_config`, and ensure the dataset provides English reference translations (FLEURS includes these). A separate output directory (e.g. `checkpoints/es-translate`) would be needed to avoid overwriting transcription checkpoints.
- Whisper-small has weaker translation performance than Whisper-medium or Whisper-large. If translation quality is a hard requirement for a client demo, consider switching `MODEL_ID` to `openai/whisper-medium` as a separate workstream.
