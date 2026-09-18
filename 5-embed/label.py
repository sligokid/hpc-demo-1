"""
Auto-labelling: calls Ollama Llama 3 to label each transcript chunk as
positive / neutral / negative with L&D domain context, outputs JSONL training
data for future fine-tuning of xlm-roberta.

Usage:
    python 5-embed/label.py --transcripts sync/output/
    python 5-embed/label.py --transcripts sync/output/ --ollama-host localhost:11434 --model llama3

Output:
    labels/<stem>.jsonl  — one JSON object per line:
        {"chunk_text": "...", "label": "positive|neutral|negative", "file": "<stem>"}
"""

import argparse
import json
import pathlib
import re
import sys

import requests

VALID_LABELS = {"positive", "neutral", "negative"}
_CHUNK_WORDS = 200

_PROMPT_TEMPLATE = """\
You are an expert in workplace learning and development content.

Classify the sentiment of the following training video transcript chunk as one of:
  positive  — encouraging, motivating, solution-focused, celebrating success
  neutral   — factual, procedural, informational, neither positive nor negative
  negative  — warning, problem-focused, describing failure, safety risk

Respond with a single JSON object: {{"label": "<positive|neutral|negative>"}}

Chunk:
{chunk}
"""


def _split_text(text: str) -> list:
    """Split plain text into ~200-word chunks on sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks, current, current_len = [], [], 0
    for sent in sentences:
        words = sent.split()
        if current_len + len(words) > _CHUNK_WORDS and current:
            chunks.append(" ".join(current))
            current, current_len = words, len(words)
        else:
            current.extend(words)
            current_len += len(words)
    if current:
        chunks.append(" ".join(current))
    return chunks or [text]


def _call_ollama(chunk: str, model: str, ollama_host: str) -> str:
    url = f"http://{ollama_host}/api/generate"
    prompt = _PROMPT_TEMPLATE.format(chunk=chunk[:600])
    try:
        resp = requests.post(
            url,
            json={"model": model, "prompt": prompt, "format": "json", "stream": False,
                  "options": {"num_predict": 32}},
            timeout=30,
        )
    except requests.exceptions.ConnectionError:
        print(f"Error: could not connect to Ollama at {ollama_host}.", file=sys.stderr)
        sys.exit(1)

    if not resp.ok:
        print(f"Error: Ollama returned {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    raw = resp.json()["response"]
    try:
        data = json.loads(raw)
        label = str(data.get("label", "neutral")).lower().strip()
        return label if label in VALID_LABELS else "neutral"
    except (json.JSONDecodeError, KeyError):
        return "neutral"


def label_transcript(transcript_path: pathlib.Path, model: str,
                     ollama_host: str, labels_dir: pathlib.Path) -> int:
    """Label all chunks of one transcript file; write JSONL. Returns chunk count."""
    text = transcript_path.read_text()
    if not text.strip():
        return 0

    stem = transcript_path.stem.replace(".transcript", "")
    chunks = _split_text(text)
    out_path = labels_dir / f"{stem}.jsonl"

    with out_path.open("w") as f:
        for chunk in chunks:
            label = _call_ollama(chunk, model, ollama_host)
            record = {"chunk_text": chunk, "label": label, "file": stem}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return len(chunks)


def main():
    parser = argparse.ArgumentParser(
        description="Label transcript chunks via Ollama for fine-tuning data."
    )
    parser.add_argument(
        "--transcripts",
        required=True,
        metavar="DIR",
        help="Root output directory (e.g. sync/output/) containing lang/stem.transcript.txt files.",
    )
    parser.add_argument("--model", default="llama3", help="Ollama model (default: llama3).")
    parser.add_argument(
        "--ollama-host", default="localhost:11434",
        help="Ollama host:port (default: localhost:11434).",
    )
    args = parser.parse_args()

    transcripts_root = pathlib.Path(args.transcripts)
    if not transcripts_root.is_dir():
        print(f"Error: {transcripts_root} is not a directory.", file=sys.stderr)
        sys.exit(1)

    labels_dir = pathlib.Path(__file__).parent.parent / "labels"
    labels_dir.mkdir(exist_ok=True)

    transcript_files = sorted(transcripts_root.rglob("*.transcript.txt"))
    if not transcript_files:
        print("No transcript files found.", file=sys.stderr)
        sys.exit(1)

    total_chunks = 0
    for tf in transcript_files:
        print(f"Labelling {tf} ...", end=" ", flush=True)
        n = label_transcript(tf, args.model, args.ollama_host, labels_dir)
        print(f"{n} chunks -> labels/{tf.stem.replace('.transcript', '')}.jsonl")
        total_chunks += n

    print(f"\nDone: {len(transcript_files)} file(s), {total_chunks} chunks labelled.")


if __name__ == "__main__":
    main()
