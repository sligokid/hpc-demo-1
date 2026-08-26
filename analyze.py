import argparse
import json
import sys
import requests


def build_prompt(transcript):
    return (
        "You are a learning content analyst. "
        "Extract structured metadata from the following training video transcript.\n\n"
        "Return a JSON object with exactly these five fields:\n"
        '- "title": a concise title for the video (string)\n'
        '- "description": a 2-3 sentence description (string)\n'
        '- "tags": a list of keyword strings\n'
        '- "goals": a list of learning goals (what the viewer will be able to do after watching)\n'
        '- "skills": a list of skills covered\n\n'
        "Transcript:\n"
        + transcript
    )


def call_ollama(prompt, model, ollama_host):
    url = f"http://{ollama_host}/api/generate"
    try:
        response = requests.post(
            url,
            json={"model": model, "prompt": prompt, "format": "json", "stream": False},
        )
    except requests.exceptions.ConnectionError:
        print(f"Error: could not connect to Ollama at {ollama_host}. Is it running?", file=sys.stderr)
        sys.exit(1)

    if not response.ok:
        print(f"Error: Ollama returned {response.status_code}: {response.text}", file=sys.stderr)
        sys.exit(1)

    return response.json()["response"]


def analyze(transcript, model, ollama_host="localhost:11434"):
    if not transcript.strip():
        print("Error: transcript is empty.", file=sys.stderr)
        sys.exit(1)

    prompt = build_prompt(transcript)
    raw = call_ollama(prompt, model, ollama_host)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"Error: model returned invalid JSON:\n{raw}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Generate structured metadata from a training video transcript."
    )
    parser.add_argument(
        "--transcript",
        required=True,
        metavar="FILE",
        help="Path to transcript file, or - to read from stdin.",
    )
    parser.add_argument(
        "--model",
        default="llama3",
        help="Ollama model to use (default: llama3).",
    )
    parser.add_argument(
        "--ollama-host",
        default="localhost:11434",
        help="Ollama host to connect to (default: localhost:11434).",
    )
    args = parser.parse_args()

    if args.transcript == "-":
        transcript = sys.stdin.read()
    else:
        with open(args.transcript) as f:
            transcript = f.read()

    metadata = analyze(transcript, args.model, args.ollama_host)
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
