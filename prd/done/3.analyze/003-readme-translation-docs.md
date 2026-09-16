## Parent PRD

`issues/prd.md`

## What to build

Add a dedicated subsection under the Inference section of `README.md` documenting the `--task translate` flag. The subsection covers a concrete example command, the English-only output constraint, a quality note about pretrained vs fine-tuned weights, and a forward reference to the fine-tuning extension point.

See the Implementation Decisions and Further Notes sections of the parent PRD for the required content.

## Acceptance criteria

- [ ] README contains a subsection under Inference for translation mode
- [ ] Subsection includes a concrete example command: `python infer.py --model_dir checkpoints/es --audio path/to/audio.wav --task translate`
- [ ] Subsection states that `--task translate` always outputs English regardless of source language
- [ ] Subsection notes that translation quality reflects Whisper's pretrained weights, not fine-tuned translation weights
- [ ] Subsection includes a forward reference indicating that fine-tuning in translation mode is a possible future extension (pointing to `train.py`)
- [ ] Existing README content is unchanged

## Blocked by

None - can start immediately

## User stories addressed

- User story 5
- User story 6
- User story 7
- User story 10
