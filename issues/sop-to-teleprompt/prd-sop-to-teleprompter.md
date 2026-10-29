# PRD: SOP to Teleprompter Video Script (Feature 3)

## Overview

Add a reverse-direction AI workflow to the SLICK+ pipeline: take a written Standard Operating Procedure (SOP) and convert it into a teleprompter-ready video script. A subject-matter expert (SME) reviews a generated checklist artifact before recording begins. This is a standalone workflow, independent of the existing video/audio → SOP pipeline.

## Background

The client has three AI workflow requirements:
1. Video to SOP — done
2. Voice-only to SOP — done
3. SOP to video script — this PRD

The client has provided a production-ready video script template that separates Visual Cues from spoken Teleprompter Audio, with specific formatting rules for teleprompter optimisation (short sentences, spelled-out numbers, hyphenated acronyms, no bullet points in audio sections).

## Goals

- Convert any written SOP (`.sop.md`, `.md`, `.txt`, `.pdf`, `.docx`) into a structured teleprompter script
- Enforce the client's teleprompter formatting rules via the Python renderer, not just the LLM prompt
- Embed an SME review step as a lightweight checklist artifact — not an afterthought
- Follow the established local → docker → HPC delivery pattern

## Non-Goals

- PDF output (Markdown only for teleprompter scripts — they are working documents)
- Integration into `pipeline.py` (this is a standalone reverse workflow)
- New Docker base image or SIF file (reuse existing `whisper-hpc.sif`)
- Interactive review UI (checklist is a static `.teleprompter.review.md` file)

---

## Functional Requirements

### Input

- SOP files dropped into `inbox/{lang}/` alongside audio files
- Supported formats: `.sop.md`, `.md`, `.txt`, `.pdf`, `.docx`
- Text is extracted from all formats and passed as plain text to the LLM

### Output (per SOP file)

| File | Description |
|---|---|
| `results/{lang}/{stem}.teleprompter.md` | Full teleprompter script following the client template |
| `results/{lang}/{stem}.teleprompter.review.md` | SME review checklist — flags placeholders and key decisions |

### Script Structure (client template)

The generated `teleprompter.md` must contain these sections in order:

1. **Metadata block** — SOP Title, Video Goal, Estimated Runtime (auto-calculated), Target Tone
2. **Section 1: Hook & Intro (0:00–0:30)** — Visual Cue + Teleprompter Audio
3. **Section 2: Step-by-Step Walkthrough** — one sub-section per SOP procedure step, each with Visual Cue + Teleprompter Audio
4. **Section 3: Common Pitfalls & Troubleshooting** (optional, only if SOP contains warnings/notes)
5. **Section 4: Outro & Call to Action** — Visual Cue + Teleprompter Audio

### Teleprompter Formatting Rules (enforced in renderer)

- Sentences capped at 15–20 words
- Numbers written out in full (`one thousand dollars`, not `$1,000`)
- Symbols written out (`ten percent`, not `10%`)
- Acronyms hyphenated when spoken as letters (`S-O-P`, `C-R-M`)
- No bold or bullet points inside Teleprompter Audio blocks
- Line breaks used to indicate natural pauses
- `[Presenter Name]` placeholder in Hook (not auto-filled)

### Runtime Estimate

Auto-calculated in Python renderer: count words in all Teleprompter Audio sections, divide by 140 wpm (midpoint of 130–150), round to nearest 30 seconds. Output as `~X min Y sec`.

### SME Review Checklist (`teleprompter.review.md`)

A static checklist written alongside the script. Contains:
- [ ] Presenter name filled in (search for `[Presenter Name]`)
- [ ] All `[bracketed placeholders]` resolved
- [ ] Step sequence matches the current SOP version
- [ ] Warnings/compliance notes included where required
- [ ] Estimated runtime is acceptable
- [ ] Sign-off line: `Reviewed by: _______ Date: _______`

---

## Technical Design

### New Files

| Path | Description |
|---|---|
| `11-sop/teleprompter.py` | Main script: input parsing, LLM call, renderer, CLI |
| `11-sop/ollama_utils.py` | Shared `_call_ollama()` extracted from `sop.py` |
| `11-sop/teleprompter_template.md` | Client's video script template (reference for prompt) |
| `11-sop/local/run-teleprompter.sh` | Local entry point |
| `11-sop/docker/Dockerfile` | Docker image (reuses whisper-hpc deps) |
| `11-sop/docker/run-teleprompter.sh` | Docker entry point |
| `11-sop/hpc/teleprompter-sbatch.sh` | SLURM sbatch script (uses `whisper-hpc.sif`) |
| `11-sop/test_teleprompter.py` | Unit tests (mocked Ollama) |

### Modified Files

| Path | Change |
|---|---|
| `11-sop/sop.py` | Import `_call_ollama` from `ollama_utils.py` instead of defining it inline |

### LLM Interaction

- Same Ollama backend as `sop.py` (`qwen2.5:7b` default, configurable)
- LLM returns structured JSON with keys: `metadata`, `hook`, `steps`, `pitfalls`, `outro`
- Python renderer converts JSON → Markdown, enforcing all formatting rules
- JSON-then-render approach (not raw Markdown from LLM) for reliable output

### CLI Interface

```bash
python 11-sop/teleprompter.py \
    --sop inbox/en/my-procedure.sop.md \
    --output results/en/my-procedure \
    --ollama-host localhost:11434 \
    --model qwen2.5:7b
```

Outputs:
- `results/en/my-procedure.teleprompter.md`
- `results/en/my-procedure.teleprompter.review.md`

### Idempotency

If both output files already exist, skip processing (same `.done`-style guard as `sop.py`).

---

## Delivery Stages

### Stage 1: Local

- `teleprompter.py` with full input parsing, LLM call, renderer, checklist writer
- `ollama_utils.py` shared utility (refactor `sop.py` to use it)
- `local/run-teleprompter.sh`
- `test_teleprompter.py` passing

### Stage 2: Docker

- `docker/Dockerfile` (reuse whisper-hpc base deps)
- `docker/run-teleprompter.sh`
- Verified end-to-end with a sample SOP file

### Stage 3: HPC

- `hpc/teleprompter-sbatch.sh` using `whisper-hpc.sif` via Singularity
- Follows same `SLURM_SUBMIT_DIR` + `--bind "$PROJECT_ROOT:/workspace"` conventions as existing HPC scripts
- Tested on a SLURM queue with a real SOP input

---

## Acceptance Criteria

- Given a `.sop.md` input, `teleprompter.py` produces a `.teleprompter.md` with all four sections present
- Runtime estimate is auto-calculated and present in the metadata block
- `[Presenter Name]` placeholder is present in the Hook
- `.teleprompter.review.md` checklist is written alongside the script
- Numbers and acronyms in audio sections follow the formatting rules
- No bullet points or bold text inside Teleprompter Audio blocks
- `test_teleprompter.py` passes with mocked Ollama (no live service required)
- Re-running on an already-processed file is a no-op
- HPC script runs successfully inside `whisper-hpc.sif` without a new SIF
