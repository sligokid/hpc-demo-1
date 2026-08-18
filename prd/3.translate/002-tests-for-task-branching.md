## Parent PRD

`issues/prd.md`

## What to build

A test module that verifies the externally observable behaviour of the `transcribe()` function in `infer.py` for both task modes. `WhisperProcessor` and `WhisperForConditionalGeneration` are mocked so no real model weights are loaded. The tests assert that `get_decoder_prompt_ids()` is called with the correct `task` argument and that the function returns a non-empty string in each case.

See the Testing Decisions section of the parent PRD for the full approach.

## Acceptance criteria

- [ ] A test file exists (e.g. `tests/test_infer.py`) that can be run with `pytest` from the repo root
- [ ] Test asserts `get_decoder_prompt_ids()` is called with `task="translate"` when `task="translate"` is passed to `transcribe()`
- [ ] Test asserts `get_decoder_prompt_ids()` is called with `task="transcribe"` when `task="transcribe"` (or the default) is passed
- [ ] Test asserts the return value is a non-empty string in both cases
- [ ] No real Whisper weights are loaded during the test run (mocks only)
- [ ] All tests pass: `pytest tests/test_infer.py`

## Blocked by

- Blocked by `issues/001-add-task-flag-to-infer.md`

## User stories addressed

- Testing Decisions section of the parent PRD
