## Parent PRD

`prd/task-2-company-brain/prd.md`

## Problem

`analyze.py` feeds the full transcript as a prompt to Ollama. `llama3` (8B) has an 8192-token context window. For long videos this causes Ollama to silently truncate the prompt before the model sees it:

```
WARN: truncating input prompt  limit=4108  prompt=23387  keep=24  new=4108
```

A 23,387-token prompt (a ~60-minute video) was cut to 4,108 tokens — 82% of the transcript was never seen by the model. The workaround in `analyze.py` pre-truncates to 3,000 words (~2,300 tokens) so at least the truncation is explicit and consistent, but it still means only the first ~20 minutes of a long video inform the metadata.

## What to build

Swap `llama3` for a model with a context window large enough to hold a full-length transcript without truncation. The pipeline config already exposes `analyze.model` in `pipeline.yaml` — this is a one-line config change once the model is chosen and pulled on the HPC node.

## Model options

| Model | Context window | Notes |
|---|---|---|
| `llama3` (current) | 8k | Too small for videos >~15 min |
| `llama3.1:8b` | 128k | Same size, much larger context — easiest swap |
| `llama3.1:70b` | 128k | Better quality, needs ~40 GB VRAM |
| `mistral-nemo` | 128k | Compact 12B model, strong JSON output |
| `gemma2:27b` | 8k | Better compression than llama3 but same window |

`llama3.1:8b` is the lowest-friction upgrade — identical pull command, same `pipeline.yaml` model name change, 128k context handles any realistic video transcript.

## Acceptance criteria

- [ ] `analyze.model` in `pipeline.yaml` updated to `llama3.1:8b` (or chosen model)
- [ ] Model pulled on HPC node: `ollama pull llama3.1:8b`
- [ ] `_MAX_TRANSCRIPT_WORDS` guard in `analyze.py` raised or removed once confirmed safe
- [ ] A 60-minute transcript processes without the Ollama truncation warning
- [ ] Existing tests still pass

## Blocked by

None — can start immediately alongside other work.
