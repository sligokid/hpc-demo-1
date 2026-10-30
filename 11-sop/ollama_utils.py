"""Shared Ollama HTTP client used by sop.py and teleprompter.py."""

import sys
import requests


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
