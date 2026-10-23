# PRD: Video to SOP Generation — Pipeline Stage 11

## Problem Statement

The pipeline currently transcribes instructional videos and extracts structured metadata (title, description, tags, goals, skills). However, the output stops at a JSON file. Operators who need to turn a training video into a usable Standard Operating Procedure (SOP) must do so manually, which is slow and inconsistent. There is no automated way to go from a video transcript to a formatted, company-branded SOP document ready for distribution.

## Solution

A new pipeline stage (`11-sop`) reads the transcript and existing `analysis.json` for each processed video, sends them to a local Qwen model via Ollama with a structured SOP prompt, and writes both a Markdown and a PDF version of the filled SOP to the results directory. The Ollama prompt injects the full contents of `11-sop/sop_template.md` — the canonical SOP template — so the LLM fills in the exact structure operators expect rather than inferring a layout. Static org fields (company name, department, approver, document number prefix) are read from a dedicated `sop_config.yaml`. Document numbers are auto-incremented and persisted in that config file. The transcript truncation limit that currently constrains `analyze.py` is made configurable so HPC runs use the full transcript for both analysis and SOP generation.

The feature is built in three stages: local Python first, then Docker, then HPC (Singularity/SLURM) — matching the established pattern of every other module in this project.

## Pipeline Position

```
infer → analyze → sentiment → embed → index → sop
```

The SOP stage runs last. It reads:
- `results/{lang}/{stem}.transcript.txt` — full transcript
- `results/{lang}/{stem}.analysis.json` — title, goals, skills from analyze stage

It writes:
- `results/{lang}/{stem}.sop.md` — Markdown SOP
- `results/{lang}/{stem}.sop.pdf` — PDF SOP (via weasyprint: Markdown → HTML → PDF)

## User Stories

1. As an operator, I want a SOP document generated automatically when a video is processed, so that I do not have to manually write it from the transcript.
2. As an operator, I want the SOP to follow a standard template (Purpose, Scope, Responsibilities, Materials, Procedure, Associated Documents, Revision History), so that all SOPs have a consistent structure.
3. As an operator, I want the Procedure section to be broken into logical sub-sections inferred from the video content, so that the SOP reflects what the video actually demonstrates without being forced into a fixed skeleton.
4. As an operator, I want both a Markdown and a PDF version of the SOP, so that I have an editable source and a distributable document.
5. As an operator, I want the PDF to be professionally formatted and readable, so that it can be handed to staff without further editing.
6. As an administrator, I want company name, department, approver, and document number prefix stored in a config file, so that all generated SOPs share the same org metadata without repeating it on the command line.
7. As an administrator, I want document numbers to auto-increment, so that each SOP gets a unique, traceable identifier without manual tracking.
8. As an administrator, I want fields the video cannot provide (Effective Date, Document Number suffix) to appear as `[Insert ...]` placeholders, so that a human can complete them without hunting for where they belong.
9. As a developer, I want SOP generation to be a feature-flagged stage in `pipeline.yaml` (`sop.enabled: true/false`), so that it can be disabled without code changes.
10. As a developer, I want `sop.py` to accept `--transcript`, `--analysis`, `--config`, `--ollama-host`, and `--model` flags for standalone use, so that I can generate a SOP for a single file without running the full pipeline.
11. As a developer, I want the transcript truncation limit to be a configurable `max_transcript_words` key in `pipeline.yaml`, so that local runs keep the existing 3000-word cap while HPC runs process the full transcript.
12. As a developer, I want the same `max_transcript_words` key to apply to both `analyze.py` and `sop.py`, so that the behaviour is consistent and controlled from one place.
13. As a developer, I want the SOP stage to reuse the existing Ollama call pattern from `analyze.py`, so that there is no new HTTP client code to maintain.
14. As a developer, I want `sop.py` to skip generation if both `.sop.md` and `.sop.pdf` already exist, consistent with the pipeline's done-flag pattern.
15. As a developer, I want the SOP stage to run inside Docker locally, so that weasyprint's system dependencies (libpango, libcairo) are contained and do not require host installation.
16. As a developer, I want the SOP stage to run inside Singularity on HPC with the same bind-mount and `SLURM_SUBMIT_DIR` conventions used by every other HPC module, so that the deployment pattern is consistent.
17. As a developer, I want a larger Ollama model (configurable) used on HPC for higher-quality SOP output, so that the document quality benefits from the available GPU resources.
18. As a developer, I want `11-sop/local/`, `11-sop/docker/`, and `11-sop/hpc/` directories following the structure of `3-analyze/` and `10-agent/`, so that the module layout is predictable.
19. As a developer, I want a test suite for `sop.py` that mocks the Ollama HTTP call and asserts correct Markdown structure and PDF file creation, so that regressions are caught without a running Ollama instance.
20. As a developer, I want the SOP prompt to include the analysis metadata (title, goals, skills) alongside the transcript, so that the LLM has richer context and produces more accurate Purpose, Scope, and Responsibilities sections.

## Implementation Decisions

### Stage 1 — Local Python

**`11-sop/sop.py`**

Core module. Responsibilities:
- Load `sop_config.yaml` for static org fields and current doc counter.
- Increment and persist the doc counter atomically before generating.
- Build a prompt combining transcript + analysis JSON + org fields.
- Call Ollama (`/api/generate`) using the Qwen model, requesting a JSON response with keys matching the SOP sections.
- Render the JSON response into the Markdown template.
- Write `{stem}.sop.md`.
- Convert Markdown → HTML → PDF via `weasyprint` + `markdown` Python library.
- Write `{stem}.sop.pdf`.

**`11-sop/sop_config.yaml`** (committed to repo with placeholder values):
```yaml
company_name: "[Insert Company Name]"
department: "[Insert Department]"
approver: "[Insert Approver Name/Title]"
doc_number_prefix: "SOP"
doc_counter: 0          # auto-incremented on each generation; commit changes
```

**`pipeline.yaml` additions:**
```yaml
sop:
  enabled: true
  model: qwen2.5:7b         # override to larger model on HPC
  config: 11-sop/sop_config.yaml

max_transcript_words: 3000  # set to 0 on HPC for no limit
```

**`3-analyze/analyze.py` change:**
Replace hardcoded `_MAX_TRANSCRIPT_WORDS = 3000` constant. The pipeline passes `max_transcript_words` from config; `analyze()` gains an optional `max_words=3000` parameter (default preserves current local behaviour). On HPC, pipeline passes `0`.

**SOP prompt structure:**
The prompt includes the full contents of `11-sop/sop_template.md` and instructs the model to return a JSON object with keys matching the template sections:
`purpose`, `scope`, `responsibilities` (list), `materials` (list), `procedure` (list of `{heading, steps}` objects), `associated_documents` (list).

The Markdown renderer maps these keys back into the template, replacing the `[Insert ...]` placeholders with generated content. Fields not derivable from the video (`company_name`, `department`, `approver`, `doc_number`, `effective_date`, `version`) are injected from `sop_config.yaml` or left as `[Insert ...]` placeholders for human completion.

**Markdown → PDF:**
`markdown` library converts `.sop.md` to HTML. A minimal CSS stylesheet embedded in the HTML provides print-ready typography (page margins, heading styles, table borders). `weasyprint` renders to PDF. The stylesheet lives at `11-sop/sop_style.css`.

### Stage 2 — Docker

**`11-sop/docker/Dockerfile`:**
Extends the project's base Python image. Adds `weasyprint` and its system dependencies (`libpango-1.0-0`, `libcairo2`, `libgdk-pixbuf2.0-0`, `libffi-dev`, fonts). Installs `markdown`, `requests`, `pyyaml`.

**`11-sop/docker/build.sh`** — builds the image.
**`11-sop/docker/run.sh`** — runs `sop.py` for a single file, binding the project root as `/workspace`.

The pipeline.py Docker variant sets `OLLAMA_HOST` via environment variable, consistent with the existing `--ollama-host` pattern.

### Stage 3 — HPC (Singularity/SLURM)

**`11-sop/hpc/build-sif.sh`** — converts the Docker image to a `.sif` file, stored in scratch alongside `whisper-hpc.sif`.

**`11-sop/hpc/submit-sop.sh`** — SLURM batch script. Array job: one task per pending transcript. Reads `SLURM_SUBMIT_DIR` for project root binding. Sets `max_transcript_words: 0` via config override or environment. Uses a larger Qwen model (e.g. `qwen2.5:72b` or `qwen2.5:14b`) configured in the HPC pipeline config. Follows the `singularity exec ... bash -c "..."` wrapper convention for `LD_LIBRARY_PATH` passthrough.

**`11-sop/hpc/run-sop.sh`** — interactive `srun` wrapper for a single transcript. Reads Ollama endpoint from the scratch discovery file (consistent with `3-analyze/hpc/` pattern).

**HPC pipeline config** (`pipeline.hpc.yaml` or env override):
```yaml
sop:
  model: qwen2.5:14b   # or larger
max_transcript_words: 0
```

### Key architectural decisions

- **JSON intermediate format** — The LLM returns structured JSON, not raw Markdown prose. This gives reliable section extraction and allows the Markdown renderer to apply consistent formatting regardless of model verbosity.

- **`weasyprint` inside Docker/Singularity** — weasyprint requires `libpango`, `libcairo`, and font packages. These are system-level deps that would pollute a local dev environment. Containerising them is the correct isolation boundary; the container already exists for every other stage.

- **Shared Qwen/Ollama service on HPC** — The SOP stage reuses the persistent Ollama service pattern established in `3-analyze/hpc/`. No new service infrastructure needed; `submit-sop.sh` reads the same endpoint discovery file.

- **`max_transcript_words: 0` = no limit** — Zero is a natural sentinel value, avoids a separate boolean flag, and is consistent with how limits work in most tooling.

- **Doc counter persisted in `sop_config.yaml`** — Keeps the counter co-located with the other config it relates to. The file is committed to the repo; each generated SOP means a one-line diff in `sop_config.yaml`. Simpler than a separate state file.

- **Analysis JSON feeds the prompt** — Title, goals, and skills extracted by `analyze.py` are injected into the SOP prompt. This reduces the burden on the SOP LLM call and produces more coherent Purpose and Scope sections without repeating the full extraction task.

### Directory layout

```
11-sop/
    sop.py                  # core module
    sop_config.yaml         # org metadata + doc counter
    sop_style.css           # PDF stylesheet
    test_sop.py             # test suite
    local/
        run.sh              # run sop.py locally against a single file
    docker/
        Dockerfile
        build.sh
        run.sh
    hpc/
        build-sif.sh
        submit-sop.sh       # SLURM array job
        run-sop.sh          # srun interactive wrapper
```

## Testing Decisions

**What to test:**

- **`sop.py` — prompt construction:** given a transcript and analysis dict, assert the Ollama payload contains the transcript text and the analysis title/goals. Mock `requests.post`.
- **`sop.py` — Markdown output:** given a mocked Ollama response with known JSON, assert the output `.sop.md` contains the expected section headings.
- **`sop.py` — PDF creation:** assert a non-empty `.sop.pdf` file is written alongside the Markdown file.
- **`sop.py` — doc counter increment:** assert `sop_config.yaml` `doc_counter` increases by 1 after a successful run.
- **`sop.py` — skip if already done:** assert Ollama is not called if both `.sop.md` and `.sop.pdf` already exist.
- **`sop.py` — truncation:** assert transcript is truncated to `max_words` when set > 0, and untruncated when 0.
- **`analyze.py` — `max_words` parameter:** assert truncation respects the new parameter; assert existing default (3000) is unchanged.

**Approach:** pytest, mock `requests.post` at the HTTP boundary. No Ollama instance required. PDF assertion checks file size > 0; full visual validation is a manual step.

## Out of Scope

- Multi-language SOP generation (the LLM generates in the language of the transcript; no translation step).
- A web UI for SOP review or editing.
- Direct DOCX output (Markdown + PDF covers the required formats; DOCX can be added later via `python-docx` if needed).
- SOP versioning or diff tracking beyond the `doc_counter` increment.
- Automatic submission of the SOP to a document management system.
- Support for videos without a transcript (the stage skips gracefully if no transcript file is found).
- Fine-tuning the Qwen model on domain-specific SOPs.

## Further Notes

- The `qwen2.5:7b` model fits comfortably in the 128k context window; a 1-hour instructional video transcript (~9000 words, ~12k tokens) is well within limits. No truncation is needed even locally, but the `max_transcript_words: 3000` default is kept to preserve fast local iteration speed.
- On HPC, `qwen2.5:14b` is the recommended minimum for SOP generation quality. `qwen2.5:72b` is preferred if GPU memory allows.
- The `sop_style.css` stylesheet should include `@page` margins, a clean sans-serif font stack, and bordered tables. A minimal A4-sized layout is sufficient for v1.
- The doc counter write should use a read-modify-write with a file lock if concurrent pipeline runs on the same machine are possible (e.g. multiple Docker containers sharing the project root). For v1, single-process operation is assumed and no lock is needed.
- If the Ollama response is not valid JSON, `sop.py` should write the raw text to `.sop.md` with a warning header rather than crashing, so the operator has something to work with even on a bad LLM response.
