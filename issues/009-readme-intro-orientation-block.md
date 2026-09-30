## Parent PRD

`prd/task-2-company-brain/prd.md`

## Status: diagram fixed by PR #9 (`75f26b0`), prose block still missing

PR #9 replaced the stale three-stage diagram with a complete nine-stage one. The remaining gap is the orientation prose.

## Problem

`README.md` still opens with a title, a single goal line, and then a 76-line ASCII diagram:

```
# SLICK+ HPC Demo — Multilingual Whisper Fine-Tuning & Knowledge Extraction Pipeline

**Goal: Turning speech & video into machine-readable knowledge at HPC scale.**

---

## Pipeline Overview

```
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                          STAGE 1: TRAINING                               │
```

The diagram is now accurate and complete, which resolves the original staleness complaint. But a reader still has to decode an ASCII box diagram to learn what the system does. The prose orientation is still absent.

## What to build

Add a short **"What this is"** prose block immediately after the goal line, before the `## Pipeline Overview` heading. It should orient a first-time reader in plain language, without requiring them to know LUMI, SLURM, or Singularity — and without making them decode the diagram.

The block should cover:

- **What the system does end to end** — audio/video in, machine-readable knowledge out: transcript, sentiment, structured metadata, semantic search index, knowledge graph.
- **The nine stages by name** — train, infer, analyze, file-sync, sentiment, embed, index, search, graph. The diagram now shows all nine, but only as boxes; naming them in prose makes them greppable and linkable to the per-stage READMEs.
- **The five languages** — en, es, fr, zh-CN, ar, each with its own fine-tuned Whisper checkpoint. Note the diagram at `README.md:13` says `zh-CN`; be aware this conflicts with `pipeline.yaml:15`, which says `zh` — see `issues/015-zh-language-code-mismatch-checkpoint-path.md`. Do not paper over it in the prose; state whichever code is canonical once that issue is resolved.
- **The operating model** — runs unattended on LUMI via eight self-resubmitting SLURM jobs; no cron, no manual babysitting. PR #9's job table already says "Eight self-resubmitting SLURM jobs" — reuse that framing.
- **Where the data lives** — Google Drive is the human-facing surface, Lustre scratch is the working store, Qdrant is the queryable index.
- **A pointer onward** — to the per-stage component docs, and to the Automated HPC Pipeline section for operational detail.

Keep it to roughly one screen. The block is orientation, not reference — specifics stay in the component READMEs and the diagram below it.

## Acceptance criteria

- [ ] `README.md` has a `## What this is` section between the goal line and `## Pipeline Overview`
- [ ] The section names all nine pipeline stages
- [ ] The section states the five supported language codes
- [ ] The section explains the unattended LUMI operating model (eight self-resubmitting SLURM jobs)
- [ ] The section links onward to the component documentation and the Automated HPC Pipeline section
- [ ] The section is under ~200 words
- [ ] The `## Pipeline Overview` diagram and all content below it are unchanged
- [ ] The Mandarin code stated matches whatever `issues/015-zh-language-code-mismatch-checkpoint-path.md` resolves to

## Blocked by

- None - can start immediately, except for the single Mandarin code token, which should match `issues/015-zh-language-code-mismatch-checkpoint-path.md` if that lands first.

## User stories addressed

- A new team member can answer "what does this project actually do?" from the first screen of the README, without reading the code or decoding an ASCII diagram.
- The nine stages are named in greppable prose, not only drawn as boxes.
