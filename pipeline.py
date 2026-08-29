"""
Pipeline orchestrator: for each audio file in inbox/{lang}/, run infer then analyze.

Reuses:
  2-inference/infer-30-secs.py  -> transcribe()
  3-analyze/analyze.py          -> analyze()

Usage:
    python pipeline.py
    python pipeline.py --config pipeline.yaml --lang en
    python pipeline.py --ollama-host 10.0.0.5:11434

Done flagging:
    A sidecar <filename>.done is written next to the audio file after both stages
    succeed. Re-runs skip files that already have a sidecar.

Output per file:
    results/{lang}/{stem}.transcript.txt   — Whisper transcript
    results/{lang}/{stem}.analysis.json    — Llama structured metadata
"""

import argparse
import importlib.util
import json
import pathlib
import sys

import yaml

PROJECT_ROOT = pathlib.Path(__file__).parent


def _import_from(module_name: str, file_path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Lazy-load so missing deps only fail at runtime for that stage
def _get_transcribe():
    mod = _import_from("infer", PROJECT_ROOT / "2-inference" / "infer-30-secs.py")
    return mod.transcribe


def _get_analyze():
    mod = _import_from("analyze", PROJECT_ROOT / "3-analyze" / "analyze.py")
    return mod.analyze


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# File scanning
# ---------------------------------------------------------------------------

def find_pending(inbox: pathlib.Path, languages: list,
                 extensions: list) -> list:
    exts = {e.lower() for e in extensions}
    pending = []
    for lang in languages:
        lang_dir = inbox / lang
        if not lang_dir.is_dir():
            continue
        for audio in sorted(lang_dir.iterdir()):
            if audio.suffix.lower() not in exts:
                continue
            if (audio.parent / (audio.name + ".done")).exists():
                continue
            pending.append((audio, lang))
    return pending


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run infer → analyze pipeline per audio file.")
    parser.add_argument("--config", default="pipeline.yaml")
    parser.add_argument("--lang", default=None, help="Restrict to one language code")
    parser.add_argument("--ollama-host", default=None,
                        help="Override ollama_host from config")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.ollama_host:
        cfg["analyze"]["ollama_host"] = args.ollama_host

    inbox = PROJECT_ROOT / cfg["inbox"]
    checkpoints = PROJECT_ROOT / cfg["checkpoints"]
    results = PROJECT_ROOT / cfg["results"]
    languages = [args.lang] if args.lang else cfg["languages"]
    extensions = cfg["infer"].get("audio_extensions", [".mp3", ".wav", ".flac"])
    infer_enabled = cfg["infer"].get("enabled", True)
    analyze_enabled = cfg["analyze"].get("enabled", True)
    ollama_host = cfg["analyze"]["ollama_host"]
    analyze_model = cfg["analyze"]["model"]

    pending = find_pending(inbox, languages, extensions)
    if not pending:
        print("No pending files found.")
        return

    print(f"Ollama host : {ollama_host}")
    print(f"Files       : {len(pending)}\n")

    transcribe = _get_transcribe() if infer_enabled else None
    analyze = _get_analyze() if analyze_enabled else None

    errors = 0

    for audio_path, lang in pending:
        stem = audio_path.stem
        out_dir = results / lang
        out_dir.mkdir(parents=True, exist_ok=True)
        transcript_file = out_dir / f"{stem}.transcript.txt"
        analysis_file = out_dir / f"{stem}.analysis.json"
        done_flag = audio_path.parent / (audio_path.name + ".done")

        print(f"[{lang}] {audio_path.name}")

        # --- Infer ---
        if infer_enabled:
            model_dir = checkpoints / lang
            if not model_dir.is_dir():
                print(f"  SKIP — no checkpoint at {model_dir}")
                errors += 1
                continue
            try:
                transcript = transcribe(str(model_dir), str(audio_path))
            except Exception as exc:
                print(f"  INFER ERROR — {exc}")
                errors += 1
                continue
            transcript_file.write_text(transcript + "\n")
            print(f"  transcript -> {transcript_file.relative_to(PROJECT_ROOT)}")
            print(f"  preview    : {transcript[:100]}")
        else:
            if not transcript_file.exists():
                print(f"  SKIP — infer disabled and no transcript at {transcript_file}")
                errors += 1
                continue
            transcript = transcript_file.read_text()

        # --- Analyze ---
        if analyze_enabled:
            try:
                metadata = analyze(transcript, analyze_model, ollama_host)
            except Exception as exc:
                print(f"  ANALYZE ERROR — {exc}")
                errors += 1
                continue
            analysis_file.write_text(json.dumps(metadata, indent=2) + "\n")
            print(f"  analysis   -> {analysis_file.relative_to(PROJECT_ROOT)}")

        # --- Flag as done ---
        done_flag.touch()
        print(f"  done       -> {done_flag.name}")

    succeeded = len(pending) - errors
    print(f"\nFinished: {succeeded}/{len(pending)} succeeded, {errors} failed.")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
