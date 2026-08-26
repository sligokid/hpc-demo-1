import argparse
import json
import sys
import requests


OLLAMA_URL = "http://localhost:11434/api/generate"


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


def call_ollama(prompt, model):
    response = requests.post(
        OLLAMA_URL,
        json={"model": model, "prompt": prompt, "format": "json", "stream": False},
    )
    response.raise_for_status()
    return response.json()["response"]


def analyze(transcript, model):
    prompt = build_prompt(transcript)
    raw = call_ollama(prompt, model)
    return json.loads(raw)


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
    args = parser.parse_args()

    if args.transcript == "-":
        transcript = sys.stdin.read()
    else:
        with open(args.transcript) as f:
            transcript = f.read()

    metadata = analyze(transcript, args.model)
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
