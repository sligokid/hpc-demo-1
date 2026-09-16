## Parent PRD

`issues/prd.md`

## What to build

Add a `--task` flag to `infer.py` that lets the caller choose between `transcribe` (default) and `translate` (English output regardless of source language). The flag is wired into `get_decoder_prompt_ids()` so Whisper's pretrained translation head is used when requested. The terminal output label changes to reflect the active task. Existing calls without `--task` continue to work identically.

See the Interface and Implementation Decisions sections of the parent PRD for the exact signature and constraints.

## Acceptance criteria

- [ ] `infer.py` accepts `--task` with `choices=["transcribe", "translate"]` and `default="transcribe"`
- [ ] When `--language` is set, `get_decoder_prompt_ids()` is called with both `language` and `task` values
- [ ] When `--language` is not set and `--task translate` is passed, `get_decoder_prompt_ids()` is called with `task="translate"` (no language override)
- [ ] Terminal prints `"Translation:"` when `--task translate` is active, `"Transcription:"` otherwise
- [ ] `python infer.py --model_dir checkpoints/es --audio audio.wav` (no `--task`) works identically to before this change

## Blocked by

None - can start immediately

## User stories addressed

- User story 1
- User story 2
- User story 3
- User story 4
- User story 8
- User story 9
