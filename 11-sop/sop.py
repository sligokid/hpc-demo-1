"""
SOP Generator: transcript + analysis.json -> {stem}.sop.md (+ .sop.pdf via issue 070)

Usage:
    python sop.py --transcript results/en/myvideo.transcript.txt \
                  --analysis  results/en/myvideo.analysis.json \
                  --output    results/en/myvideo \
                  --config    11-sop/sop_config.yaml \
                  --ollama-host localhost:11434 \
                  --model qwen2.5:7b
"""

import argparse
import json
import pathlib
import sys

import requests
import yaml


TEMPLATE_PATH = pathlib.Path(__file__).parent / "sop_template.md"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_config(config_path: pathlib.Path) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Transcript truncation
# ---------------------------------------------------------------------------

def _truncate_transcript(transcript: str, max_words: int) -> str:
    if max_words == 0:
        return transcript
    words = transcript.split()
    if len(words) <= max_words:
        return transcript
    return " ".join(words[:max_words]) + "\n[transcript truncated]"


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

def build_prompt(transcript: str, analysis: dict, template: str, max_words: int = 0) -> str:
    title = analysis.get("title", "")
    goals = analysis.get("goals", [])
    skills = analysis.get("skills", [])

    goals_str = "\n".join(f"- {g}" for g in goals) if goals else "- (none provided)"
    skills_str = "\n".join(f"- {s}" for s in skills) if skills else "- (none provided)"

    return (
        "You are an expert SOP (Standard Operating Procedure) writer.\n"
        "Given the instructional video transcript and metadata below, generate a filled SOP.\n\n"
        "VIDEO METADATA:\n"
        f"Title: {title}\n"
        f"Learning Goals:\n{goals_str}\n"
        f"Skills Covered:\n{skills_str}\n\n"
        "TRANSCRIPT:\n"
        f"{_truncate_transcript(transcript, max_words)}\n\n"
        "SOP TEMPLATE (follow this structure exactly):\n"
        f"{template}\n\n"
        "Return a JSON object with exactly these keys:\n"
        '- "document_title": concise title for this SOP (string)\n'
        '- "purpose": clear statement of why this procedure exists (string)\n'
        '- "scope": who it applies to and what it covers (string)\n'
        '- "responsibilities": list of {"role": string, "description": string}\n'
        '- "materials": list of strings\n'
        '- "procedure": list of {"heading": string, "steps": list of strings} — heading must be a plain title with NO numbering (e.g. "Packing", not "5.1. Packing")\n'
        '- "associated_documents": list of {"name": string, "description": string}\n'
    )


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

def _call_ollama(prompt: str, model: str, ollama_host: str) -> str:
    url = f"http://{ollama_host}/api/generate"
    try:
        resp = requests.post(
            url,
            json={"model": model, "prompt": prompt, "format": "json", "stream": False},
            timeout=600,
        )
    except requests.exceptions.ConnectionError:
        print(f"Error: could not connect to Ollama at {ollama_host}. Is it running?", file=sys.stderr)
        sys.exit(1)

    if not resp.ok:
        print(f"Error: Ollama returned {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    return resp.json()["response"]


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

def _render_markdown(data: dict, cfg: dict) -> str:
    lines = [
        "# STANDARD OPERATING PROCEDURE (SOP)",
        "",
        f"**Company Name:** {cfg.get('company_name', '[Insert Company Name]')}",
        f"**Department:** {cfg.get('department', '[Insert Department]')}",
        f"**Document Title:** {data.get('document_title', '[Insert Document Title]')}",
        "**Document Number:** [Insert Document Number]",
        "**Version:** 1.0",
        "**Effective Date:** [Insert Effective Date]",
        f"**Approved By:** {cfg.get('approver', '[Insert Name/Title of Approver]')}",
        "",
        "---",
        "",
        "## 1. PURPOSE",
        "",
        data.get("purpose", "[Insert purpose]"),
        "",
        "---",
        "",
        "## 2. SCOPE",
        "",
        data.get("scope", "[Insert scope]"),
        "",
        "---",
        "",
        "## 3. RESPONSIBILITIES",
        "",
    ]

    for r in data.get("responsibilities", []):
        lines.append(f"- **{r.get('role', 'Role')}:** {r.get('description', '')}")
    if not data.get("responsibilities"):
        lines.append("- [Insert responsibilities]")

    lines += ["", "---", "", "## 4. MATERIALS AND EQUIPMENT REQUIRED", ""]

    for m in data.get("materials", []):
        lines.append(f"- {m}")
    if not data.get("materials"):
        lines.append("- [Insert materials]")

    lines += ["", "---", "", "## 5. PROCEDURE", ""]

    for i, section in enumerate(data.get("procedure", []), start=1):
        lines.append(f"### 5.{i}. {section.get('heading', 'Step')}")
        lines.append("")
        for j, step in enumerate(section.get("steps", []), start=1):
            lines.append(f"{j}. {step}")
        lines.append("")

    if not data.get("procedure"):
        lines.append("- [Insert procedure steps]")

    lines += ["---", "", "## 6. ASSOCIATED DOCUMENTS & REFERENCES", ""]

    for doc in data.get("associated_documents", []):
        lines.append(f"- **{doc.get('name', 'Document')}:** {doc.get('description', '')}")
    if not data.get("associated_documents"):
        lines.append("- [Insert associated documents]")

    lines += [
        "",
        "---",
        "",
        "## 7. REVISION HISTORY",
        "",
        "| Version | Date | Changes Made | Author |",
        "|---|---|---|---|",
        "| 1.0 | [Insert Date] | Initial generation from video transcript | [Insert Author] |",
    ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate(
    transcript: str,
    analysis: dict,
    output_stem: pathlib.Path,
    config_path: pathlib.Path,
    ollama_host: str = "localhost:11434",
    model: str = "qwen2.5:7b",
    max_words: int = 0,
) -> tuple:
    """Generate SOP Markdown from transcript + analysis. Returns (md_path, pdf_path)."""
    md_path = output_stem.parent / (output_stem.name + ".sop.md")
    pdf_path = output_stem.parent / (output_stem.name + ".sop.pdf")

    if md_path.exists() and pdf_path.exists():
        return md_path, pdf_path

    template = TEMPLATE_PATH.read_text()
    cfg = _load_config(config_path)

    prompt = build_prompt(transcript, analysis, template, max_words)
    raw = _call_ollama(prompt, model, ollama_host)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        md_path.write_text(f"<!-- WARNING: raw LLM output -->\n\n{raw}\n")
        return md_path, pdf_path

    md_path.write_text(_render_markdown(data, cfg))

    return md_path, pdf_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate an SOP from a transcript and analysis.")
    parser.add_argument("--transcript", required=True, help="Path to transcript .txt file")
    parser.add_argument("--analysis", required=True, help="Path to analysis .json file")
    parser.add_argument("--output", required=True, help="Output stem (e.g. results/en/myvideo)")
    parser.add_argument("--config", default=str(pathlib.Path(__file__).parent / "sop_config.yaml"))
    parser.add_argument("--ollama-host", default="localhost:11434")
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--max-words", type=int, default=0,
                        help="Max transcript words sent to model (0 = unlimited)")
    args = parser.parse_args()

    transcript = pathlib.Path(args.transcript).read_text()
    analysis = json.loads(pathlib.Path(args.analysis).read_text())
    output_stem = pathlib.Path(args.output)
    output_stem.parent.mkdir(parents=True, exist_ok=True)

    md_path, _ = generate(
        transcript=transcript,
        analysis=analysis,
        output_stem=output_stem,
        config_path=pathlib.Path(args.config),
        ollama_host=args.ollama_host,
        model=args.model,
        max_words=args.max_words,
    )
    print(f"SOP written -> {md_path}")


if __name__ == "__main__":
    main()
