"""
Teleprompter Script Generator: SOP file -> {stem}.teleprompter.md + {stem}.teleprompter.review.md

Usage:
    python teleprompter.py --sop inbox/en/my-procedure.sop.md \
                           --output results/en/my-procedure \
                           --ollama-host localhost:11434 \
                           --model qwen2.5:7b
"""

import argparse
import json
import pathlib
import re
import sys

from ollama_utils import _call_ollama


NUMBERS = [
    "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE", "TEN",
    "ELEVEN", "TWELVE", "THIRTEEN", "FOURTEEN", "FIFTEEN", "SIXTEEN", "SEVENTEEN",
    "EIGHTEEN", "NINETEEN", "TWENTY",
]

REVIEW_CHECKLIST = """\
# SME Review Checklist

Complete this checklist before recording begins.

- [ ] Presenter name filled in (search for `[Presenter Name]` in the teleprompter script)
- [ ] All `[bracketed placeholders]` resolved
- [ ] Step sequence matches the current version of the written S-O-P
- [ ] Warnings and compliance notes included where required
- [ ] Estimated runtime is acceptable for the intended audience
- [ ] Visual cues are achievable with available equipment or software
- [ ] Sign-off: Reviewed by: _______________________ Date: _______________
"""


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------

def _read_sop(path: pathlib.Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            print("Error: pypdf is required to read PDF files. pip install pypdf", file=sys.stderr)
            sys.exit(1)
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix == ".docx":
        try:
            import docx
        except ImportError:
            print("Error: python-docx is required to read .docx files. pip install python-docx", file=sys.stderr)
            sys.exit(1)
        doc = docx.Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    # fallback: plain text
    return path.read_text()


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

def build_prompt(sop_text: str) -> str:
    return (
        "You are an expert video script writer specialising in teleprompter scripts.\n"
        "Convert the Standard Operating Procedure below into a structured video script.\n\n"
        "FORMATTING RULES — follow these exactly:\n"
        "- Write for the ear, not the eye. Use conversational English.\n"
        "- Keep all sentences under 15 words.\n"
        "- Write out numbers in full (e.g. 'one thousand dollars', not '$1,000').\n"
        "- Write out symbols in full (e.g. 'ten percent', not '10%').\n"
        "- Hyphenate acronyms spoken as letters (e.g. 'S-O-P', 'C-R-M', 'I-D').\n"
        "- Do NOT use bullet points or bold text inside audio fields.\n"
        "- Use line breaks to indicate natural pauses.\n\n"
        "SOP TEXT:\n"
        f"{sop_text}\n\n"
        "Return a JSON object with exactly these keys:\n"
        '- "sop_title": title of the SOP (string)\n'
        '- "video_goal": one sentence — what the viewer will achieve (string)\n'
        '- "prerequisites": list of 1-3 items needed before starting (list of strings)\n'
        '- "hook_audio": conversational teleprompter intro, do NOT include "Hi, I\'m [Presenter Name]." — that line is added automatically (string)\n'
        '- "steps": list of {"name": string, "visual_cue": string, "audio": string} — one entry per SOP procedure step\n'
        '- "has_pitfalls": true if the SOP contains warnings, notes, or troubleshooting (boolean)\n'
        '- "pitfalls_visual_cue": visual cue description for the pitfalls section (string)\n'
        '- "pitfalls_audio": teleprompter text for pitfalls, empty string if has_pitfalls is false (string)\n'
        '- "outro_audio": closing text, do NOT include "That covers the process for [title]." — added automatically (string)\n'
        '- "department_or_helpdesk": team or contact for help, inferred from the SOP (string)\n'
    )


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _strip_formatting(text: str) -> str:
    """Remove bold markers and leading bullet points from audio text."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"^[\-\*]\s+", "", text, flags=re.MULTILINE)
    return text.strip()


def _count_audio_words(data: dict) -> int:
    parts = [
        data.get("hook_audio", ""),
        data.get("pitfalls_audio", ""),
        data.get("outro_audio", ""),
    ]
    for step in data.get("steps", []):
        parts.append(step.get("audio", ""))
    return sum(len(p.split()) for p in parts if p)


def _runtime_estimate(word_count: int) -> str:
    seconds = round((word_count / 140) * 60 / 30) * 30
    minutes = seconds // 60
    secs = seconds % 60
    if minutes == 0:
        return f"~{secs} sec"
    if secs == 0:
        return f"~{minutes} min"
    return f"~{minutes} min {secs} sec"


def _step_number(i: int) -> str:
    if i <= len(NUMBERS):
        return NUMBERS[i - 1]
    return str(i)


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

def _render_markdown(data: dict) -> str:
    sop_title = data.get("sop_title", "[SOP Title]")
    video_goal = data.get("video_goal", "[Video Goal]")
    prerequisites = data.get("prerequisites", [])
    hook_audio = _strip_formatting(data.get("hook_audio", ""))
    steps = data.get("steps", [])
    has_pitfalls = data.get("has_pitfalls", False)
    pitfalls_visual_cue = data.get("pitfalls_visual_cue", "Warning Icon on Screen")
    pitfalls_audio = _strip_formatting(data.get("pitfalls_audio", ""))
    outro_audio = _strip_formatting(data.get("outro_audio", ""))
    helpdesk = data.get("department_or_helpdesk", "[Department/Helpdesk]")

    word_count = _count_audio_words(data)
    runtime = _runtime_estimate(word_count)
    prereq_str = ", ".join(prerequisites) if prerequisites else "[prerequisites]"

    lines = [
        f"# {sop_title} — Teleprompter Video Script",
        "",
        "## Metadata",
        "",
        f"SOP Title: {sop_title}",
        f"Video Goal: {video_goal}",
        f"Estimated Runtime: {runtime} (at 130–150 words per minute)",
        "Target Tone: Professional, encouraging, and clear",
        "",
        "---",
        "",
        "## Section 1: Hook & Intro (0:00 – 0:30)",
        "",
        "Visual Cue: Title Card + Presenter on Camera",
        "",
        "Teleprompter Audio:",
        "",
        "Hi, I'm [Presenter Name].",
        f"Today we are going through the standard operating procedure for {sop_title}.",
        "",
        f"By the end of this video, you will know exactly how to {video_goal}.",
        "",
        f"Before we begin, make sure you have {prereq_str}.",
        "",
        hook_audio,
        "",
        "Let's get started.",
        "",
        "---",
        "",
        "## Section 2: Step-by-Step Walkthrough",
        "",
    ]

    for i, step in enumerate(steps, start=1):
        num = _step_number(i)
        name = step.get("name", f"Step {i}")
        visual_cue = step.get("visual_cue", "Screen recording")
        audio = _strip_formatting(step.get("audio", ""))
        lines += [
            f"### Step {num}: {name}",
            "",
            f"Visual Cue: {visual_cue}",
            "",
            "Teleprompter Audio:",
            "",
            audio,
            "",
        ]

    lines += ["---", ""]

    if has_pitfalls and pitfalls_audio:
        lines += [
            "## Section 3: Common Pitfalls & Troubleshooting",
            "",
            f"Visual Cue: {pitfalls_visual_cue}",
            "",
            "Teleprompter Audio:",
            "",
            pitfalls_audio,
            "",
            "---",
            "",
        ]

    lines += [
        "## Section 4: Outro & Call to Action",
        "",
        "Visual Cue: Presenter back on camera",
        "",
        "Teleprompter Audio:",
        "",
        f"That covers the process for {sop_title}.",
        "",
        outro_audio,
        "",
        "For more details, you can read the full written S-O-P linked below this video.",
        f"If you run into any blockers, reach out to the {helpdesk} team.",
        "",
        "Thanks for watching.",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate(
    sop_text: str,
    output_stem: pathlib.Path,
    ollama_host: str = "localhost:11434",
    model: str = "qwen2.5:7b",
) -> tuple:
    """Generate teleprompter script from SOP text. Returns (script_path, review_path)."""
    script_path = output_stem.parent / (output_stem.name + ".teleprompter.md")
    review_path = output_stem.parent / (output_stem.name + ".teleprompter.review.md")

    if script_path.exists() and review_path.exists():
        return script_path, review_path

    prompt = build_prompt(sop_text)
    raw = _call_ollama(prompt, model, ollama_host)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        script_path.write_text(f"<!-- WARNING: raw LLM output -->\n\n{raw}\n")
        review_path.write_text(REVIEW_CHECKLIST)
        return script_path, review_path

    md_text = _render_markdown(data)
    script_path.write_text(md_text)
    review_path.write_text(REVIEW_CHECKLIST)

    return script_path, review_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate a teleprompter script from an SOP.")
    parser.add_argument("--sop", required=True, help="Path to SOP file (.md, .txt, .pdf, .docx)")
    parser.add_argument("--output", required=True, help="Output stem (e.g. results/en/myvideo)")
    parser.add_argument("--ollama-host", default="localhost:11434")
    parser.add_argument("--model", default="qwen2.5:7b")
    args = parser.parse_args()

    sop_path = pathlib.Path(args.sop)
    if not sop_path.exists():
        print(f"Error: SOP file not found: {sop_path}", file=sys.stderr)
        sys.exit(1)

    sop_text = _read_sop(sop_path)
    output_stem = pathlib.Path(args.output)
    output_stem.parent.mkdir(parents=True, exist_ok=True)

    script_path, review_path = generate(
        sop_text=sop_text,
        output_stem=output_stem,
        ollama_host=args.ollama_host,
        model=args.model,
    )
    print(f"Script  -> {script_path}")
    print(f"Review  -> {review_path}")
    print()
    print("REVIEW REQUIRED before recording.")
    print(f"Open {review_path} and complete the checklist.")


if __name__ == "__main__":
    main()
