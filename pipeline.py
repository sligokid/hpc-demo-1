"""
Pipeline orchestrator: for each audio file in inbox/{lang}/, run infer then analyze.

Reuses:
  2-inference/infer-30-secs.py  -> transcribe()
  3-analyze/analyze.py          -> analyze()

Usage:
    python pipeline.py                                        # all pending files
    python pipeline.py --lang en                              # one language
    python pipeline.py --file inbox/en/foo.mp3                # single file (HPC array task)
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
import os
import pathlib
import sys

import requests
import yaml

PROJECT_ROOT = pathlib.Path(__file__).parent


def _import_from(module_name: str, file_path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Lazy-load so missing deps only fail at runtime for that stage
def _get_transcribe():
    mod = _import_from("infer", PROJECT_ROOT / "2-inference" / "infer.py")
    return mod.transcribe


def _get_transcribe_with_segments():
    mod = _import_from("infer", PROJECT_ROOT / "2-inference" / "infer.py")
    return mod.transcribe_with_segments


def _call_embed(server_url: str, segments: list) -> list:
    """POST /embed → returns list of {text, ts_start, ts_end, vector}."""
    payload = {
        "chunks": [
            {
                "text": s["text"],
                "timestamp_start": s["start"],
                "timestamp_end": s["end"],
            }
            for s in segments
        ],
    }
    resp = requests.post(f"{server_url}/embed", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["vectors"]


def _call_index(server_url: str, video_id: str, file_path: str, lang: str, vectors: list) -> int:
    """POST /index → returns indexed count."""
    payload = {
        "video_id": video_id,
        "file": file_path,
        "lang": lang,
        "vectors": vectors,
    }
    resp = requests.post(f"{server_url}/index", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["indexed"]


def _call_metadata(server_url: str, video_id: str, file_path: str, lang: str, analysis: dict):
    payload = {"video_id": video_id, "file": file_path, "lang": lang, **analysis}
    resp = requests.post(f"{server_url}/metadata", json=payload, timeout=30)
    resp.raise_for_status()


def _get_analyze():
    mod = _import_from("analyze", PROJECT_ROOT / "3-analyze" / "analyze.py")
    return mod.analyze


def _get_run_sentiment():
    mod = _import_from("sentiment", PROJECT_ROOT / "5-sentiment" / "sentiment.py")
    return mod.run_sentiment, mod._split_text


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
    parser.add_argument("--file", default=None,
                        help="Process a single audio file (lang inferred from parent dir name)")
    parser.add_argument("--ollama-host", default=None,
                        help="Override ollama_host from config")
    parser.add_argument("--analyze-model", default=None,
                        help="Override analyze.model from config (e.g. llama3.1:8b)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.ollama_host:
        cfg["analyze"]["ollama_host"] = args.ollama_host
    if args.analyze_model:
        cfg["analyze"]["model"] = args.analyze_model

    checkpoints = PROJECT_ROOT / cfg["checkpoints"]
    results = PROJECT_ROOT / cfg["results"]
    infer_enabled = cfg["infer"].get("enabled", True)
    analyze_enabled = cfg["analyze"].get("enabled", True)
    ollama_host = cfg["analyze"]["ollama_host"]
    analyze_model = cfg["analyze"]["model"]
    embed_enabled = cfg.get("embed", {}).get("enabled", False)
    embed_url = os.getenv("EMBEDDING_SERVER_URL", cfg.get("embed", {}).get("server_url", "http://localhost:8765"))
    index_url = os.getenv("INDEX_SERVER_URL", cfg.get("index", {}).get("server_url", "http://localhost:8766"))
    sentiment_enabled = cfg.get("sentiment", {}).get("enabled", False)

    if args.file:
        audio_path = pathlib.Path(args.file)
        lang = args.lang if args.lang else audio_path.parent.name
        pending = [(audio_path, lang)]
    else:
        inbox = PROJECT_ROOT / cfg["inbox"]
        languages = [args.lang] if args.lang else cfg["languages"]
        extensions = cfg["infer"].get("audio_extensions", [".mp3", ".wav", ".flac"])
        pending = find_pending(inbox, languages, extensions)

    if not pending:
        print("No pending files found.")
        return

    print(f"Ollama host : {ollama_host}")
    print(f"Files       : {len(pending)}\n")

    if infer_enabled:
        transcribe = _get_transcribe_with_segments() if embed_enabled else _get_transcribe()
    else:
        transcribe = None
    analyze = _get_analyze() if analyze_enabled else None
    run_sentiment, split_text = (_get_run_sentiment() if sentiment_enabled
                                 else (None, None))

    errors = 0

    for audio_path, lang in pending:
        stem = audio_path.stem
        out_dir = results / lang
        out_dir.mkdir(parents=True, exist_ok=True)
        transcript_file = out_dir / f"{stem}.transcript.txt"
        analysis_file = out_dir / f"{stem}.analysis.json"
        done_flag = audio_path.parent / (audio_path.name + ".done")

        segments_file = out_dir / f"{stem}.segments.json"
        sentiment_file = out_dir / f"{stem}.sentiment.json"
        print(f"[{lang}] {audio_path.name}")

        # --- Infer ---
        segments = None
        if infer_enabled:
            model_dir = checkpoints / lang
            if not model_dir.is_dir():
                print(f"  SKIP — no checkpoint at {model_dir}")
                errors += 1
                continue
            try:
                if embed_enabled:
                    transcript, segments = transcribe(str(model_dir), str(audio_path))
                    segments_file.write_text(json.dumps(segments, indent=2) + "\n")
                    print(f"  segments   -> {segments_file.relative_to(PROJECT_ROOT)}")
                else:
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
            if embed_enabled and segments_file.exists():
                segments = json.loads(segments_file.read_text())

        # --- Analyze ---
        metadata = None
        if analyze_enabled:
            try:
                metadata = analyze(transcript, analyze_model, ollama_host)
            except Exception as exc:
                print(f"  ANALYZE ERROR — {exc}")
                errors += 1
                continue
            analysis_file.write_text(json.dumps(metadata, indent=2) + "\n")
            print(f"  analysis   -> {analysis_file.relative_to(PROJECT_ROOT)}")

        # --- Sentiment ---
        sentiment_data = {}
        if sentiment_enabled:
            try:
                chunks = segments if segments else split_text(transcript)
                sentiment_data = run_sentiment(chunks)
                sentiment_file.write_text(json.dumps(sentiment_data, indent=2) + "\n")
                print(f"  sentiment  -> {sentiment_file.relative_to(PROJECT_ROOT)}")
                if metadata is not None:
                    metadata.update(sentiment_data)
            except Exception as exc:
                print(f"  SENTIMENT ERROR — {exc}")

        # --- Embed + Index ---
        if embed_enabled and segments:
            video_id = f"{lang}/{stem}"
            try:
                vectors = _call_embed(embed_url, segments)
                n = _call_index(index_url, video_id, str(audio_path), lang, vectors)
                print(f"  embedded   -> {n} chunks indexed")
                if metadata:
                    _call_metadata(index_url, video_id, str(audio_path), lang, metadata)
                    print(f"  metadata   -> indexed")
            except Exception as exc:
                print(f"  EMBED ERROR — {exc}")

        # --- Flag as done ---
        done_flag.touch()
        print(f"  done       -> {done_flag.name}")

    succeeded = len(pending) - errors
    print(f"\nFinished: {succeeded}/{len(pending)} succeeded, {errors} failed.")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
