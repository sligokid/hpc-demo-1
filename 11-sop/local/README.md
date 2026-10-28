# 11-sop/local — Run SOP Generation Locally

Generates a Standard Operating Procedure (`.sop.md` + `.sop.pdf`) from a transcript and analysis JSON using a local Ollama model.

---

## Prerequisites

- Ollama running locally with `qwen2.5:7b` pulled
- Python virtual environment activated with `xhtml2pdf`, `markdown`, and `requests` installed
- A completed transcript (`.transcript.txt`) and analysis (`.analysis.json`) for the target video — produced by `2-inference` and `3-analyze`

```bash
ollama pull qwen2.5:7b
source venv/bin/activate
pip install -r 11-sop/requirements.txt
```

---

## Running

```bash
bash 11-sop/local/run.sh results/en/myvideo
```

This reads:

- `results/en/myvideo.transcript.txt`
- `results/en/myvideo.analysis.json`

And writes:

- `results/en/myvideo.sop.md` — Markdown SOP document
- `results/en/myvideo.sop.pdf` — PDF rendered from the Markdown via xhtml2pdf

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL` | `qwen2.5:7b` | Ollama model to use for SOP generation |
| `OLLAMA_HOST` | `localhost:11434` | Ollama API host |

```bash
MODEL=llama3.1:8b bash 11-sop/local/run.sh results/en/myvideo
```

---

## Organisation fields

`company_name`, `department`, and `approver` are inferred from the transcript by the LLM. If they cannot be determined, the SOP header shows `N/A`.

---

## Files

| File | Role |
|------|------|
| `run.sh` | Runs `sop.py` for a single transcript/analysis pair |
