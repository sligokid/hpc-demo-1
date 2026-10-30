# 11-sop — SOP & Teleprompter Generation

Two independent pipelines that convert instructional content into structured documents using a local LLM (Ollama).

- **SOP Generation** turns a video transcript and analysis into a Standard Operating Procedure. 

- **Teleprompter Generation** turns any SOP document into a speech-optimised presenter script. 
---

## Models Used

| Model | Source | Role |
|-------|--------|------|
| `qwen2.5:7b` | Ollama | Default — generates structured JSON SOP and teleprompter scripts |
| `llama3.1:8b` | Ollama | Recommended for HPC — larger context, better JSON reliability |

Model is configurable via `--model`. Pull with `ollama pull <model>` before running.

---

## How it Works

### Flow A — SOP Generation (independent)

```
transcript.txt + analysis.json
        ↓
    sop.py  (qwen2.5:7b via Ollama)
        ↓
  .sop.md + .sop.pdf
```

`sop.py` sends the transcript and metadata (from `2-inference` / `3-analyze`) to Ollama and asks the model to return a structured JSON object. The JSON is rendered to Markdown with these sections:

1. **PURPOSE** — one-line statement of intent
2. **SCOPE** — who and what is covered
3. **RESPONSIBILITIES** — role → responsibility
4. **MATERIALS AND EQUIPMENT REQUIRED** — bulleted list
5. **PROCEDURE** — numbered sub-steps grouped under headings (5.1, 5.2, …)
6. **ASSOCIATED DOCUMENTS & REFERENCES**
7. **REVISION HISTORY** — version table seeded at 1.0

PDF is generated via xhtml2pdf with embedded CSS (`sop_style.css`). Both outputs skip generation if the files already exist (idempotent). If JSON parsing fails, the raw LLM output is written with a `<!-- WARNING: raw LLM output -->` header so the pipeline does not fail.

### Flow B — Teleprompter Generation (independent)

```
any SOP file (.md / .txt / .pdf / .docx)
        ↓
teleprompter.py  (qwen2.5:7b via Ollama)
        ↓
  .teleprompter.md  (script + SME review checklist)
```

`teleprompter.py` accepts any SOP document — not limited to the output of `sop.py`. It reads `.md`/`.txt` directly, `.pdf` via pypdf, and `.docx` via python-docx. The model returns structured JSON rendered to a presenter script:

- **SECTION 1** — Hook & Intro
- **SECTION 2** — Step-by-Step Walkthrough (STEP ONE, STEP TWO, …)
- **SECTION 3** — Common Pitfalls (if any)
- **SECTION 4/5** — Outro & Call to Action
- **SME Review Checklist** — appended after a horizontal rule

Speech constraints applied: sentences ≤15 words, numbers spelled out, symbols written out, acronyms hyphenated, `[PAUSE]` markers, no bullet points in audio fields. Runtime estimate is embedded (130–150 words/min, rounded to the nearest 30 seconds).

---

## Sample Output

**`.sop.md` excerpt (section 5)**

```markdown
## 5. PROCEDURE

### 5.1. Prepare the Workspace

1. Open the application and log in with your credentials.
2. Navigate to the Settings panel and select New Project.
3. Confirm the project template matches your department standard.

### 5.2. Run the Process

1. Upload the source file using the drag-and-drop interface.
2. Select the appropriate output format from the dropdown.
3. Click Generate and wait for the confirmation banner.
```

**`.teleprompter.md` excerpt (section 2)**

```markdown
## SECTION 2 — Step-by-Step Walkthrough

| | |
|---|---|
| **STEP ONE** | |
| Visual Cue | Screen recording: open the application |
| Audio | Open the application and log in. [PAUSE] Navigate to Settings and select New Project. [PAUSE] |

| | |
|---|---|
| **STEP TWO** | |
| Visual Cue | Screen recording: upload source file |
| Audio | Upload your source file using the drag-and-drop area. [PAUSE] Choose the output format, then click Generate. [PAUSE] |
```

---

## Files

| File | Role |
|------|------|
| `sop.py` | Transcript + analysis → structured JSON → `.sop.md` + `.sop.pdf` |
| `teleprompter.py` | Any SOP document → structured JSON → `.teleprompter.md` |
| `ollama_utils.py` | Shared Ollama HTTP helper used by both scripts |
| `sop_template.md` | LLM prompt template that guides SOP JSON structure |
| `sop_style.css` | CSS embedded in PDF output |
| `local/run.sh` | Local runner for `sop.py` |
| `local/run-teleprompter.sh` | Local runner for `teleprompter.py` |
| `docker/` | Docker Compose setup for running both scripts with containerised Ollama |
| `hpc/teleprompter-hpc-submit.sh` | Scans `sync/input/*/` for pending `.sop.md`, writes timestamped manifest, submits SLURM array |
| `hpc/teleprompter-hpc-poll.sh` | Persistent 10-min polling loop — resubmits when new SOPs arrive |
| `hpc/teleprompter-sbatch.sh` | SLURM array task — runs `teleprompter.py` via Singularity (`sop-tools.sif`) |
| `test_sop.py` | Unit tests for `sop.py` (mocked Ollama) |
| `test_teleprompter.py` | Unit tests for `teleprompter.py` (mocked Ollama) |

---

## Running locally

```bash
# SOP generation — reads <stem>.transcript.txt + <stem>.analysis.json
bash 11-sop/local/run.sh results/en/myvideo

# Teleprompter generation — reads any SOP file directly
bash 11-sop/local/run-teleprompter.sh inbox/en/my-procedure.sop.md
```

Both scripts respect `MODEL` and `OLLAMA_HOST` environment variables:

```bash
MODEL=llama3.1:8b OLLAMA_HOST=localhost:11434 bash 11-sop/local/run.sh results/en/myvideo
```

---

## Docker

```bash
# 1. Start the Ollama service
docker compose up -d ollama

# 2. Pull the model into the named volume (once)
docker compose exec ollama ollama pull qwen2.5:7b

# 3. Run sop.py inside the dev container
docker compose run --rm dev python 11-sop/sop.py \
    --transcript sync/output/en/my-video.transcript.txt \
    --analysis   sync/output/en/my-video.analysis.json \
    --output     sync/output/en/my-video \
    --ollama-host ollama:11434

# 4. Run teleprompter.py inside the dev container
docker compose run --rm dev python 11-sop/teleprompter.py \
    --sop    sync/output/en/my-video.sop.md \
    --output sync/output/en/my-video \
    --ollama-host ollama:11434
```

See `11-sop/docker/README.md` for the full Docker workflow including the pre-built image.

---

## Running on LUMI (HPC)

**SOP generation** runs on HPC as part of `pipeline.py`. 

**Teleprompter generation** is standalone (it takes arbitrary SOP files, not pipeline output) so it has its own submit/poll scripts here.

The array job reads a manifest of pending `.sop.md` files and runs one Singularity task per file.

**One-shot submit:**

```bash
bash 11-sop/hpc/teleprompter-hpc-submit.sh
```

This scans `sync/input/*/` for `.sop.md` files whose `.teleprompter.md` output does not yet exist, writes a timestamped manifest to `logs/`, and submits a SLURM array job.

**Persistent poll loop (unattended):**

```bash
bash 11-sop/hpc/teleprompter-hpc-poll.sh
```

Runs in the background; checks for new SOPs every 10 minutes and resubmits when found. Stop with:

```bash
scancel --name=G-teleprompter --user=$USER
```

**Monitor:**

```bash
squeue -u $USER
tail -f logs/<jobid>_<arrayindex>.out
```

---

## Flags

### `sop.py`

| Flag | Default | Description |
|------|---------|-------------|
| `--transcript` | required | Path to `.transcript.txt` file |
| `--analysis` | required | Path to `.analysis.json` file |
| `--output` | required | Output stem (e.g. `results/en/myvideo`) |
| `--model` | `qwen2.5:7b` | Ollama model to use |
| `--ollama-host` | `localhost:11434` | Ollama host:port |
| `--max-words` | `0` (unlimited) | Truncate transcript before sending to model |

### `teleprompter.py`

| Flag | Default | Description |
|------|---------|-------------|
| `--sop` | required | Path to SOP file (`.md`, `.txt`, `.pdf`, `.docx`) |
| `--output` | required | Output stem (e.g. `results/en/myvideo`) |
| `--model` | `qwen2.5:7b` | Ollama model to use |
| `--ollama-host` | `localhost:11434` | Ollama host:port |
