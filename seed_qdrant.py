"""
Seed Qdrant from already-produced HPC pipeline output files.

Reads *.segments.json (+ optional .analysis.json / .sentiment.json) from
sync/output/{lang}/ and calls the running 6-embed + 7-index HTTP servers.

Pre-requisites (must be running):
    7-index/local/1-start-qdrant.sh          # Qdrant on :6333
    6-embed/local/1-start-embed-server.sh    # embed server on :8765
    7-index/local/2-start-index-server.sh    # index server on :8766

Usage:
    python seed_qdrant.py                         # all langs in sync/output/
    python seed_qdrant.py --lang en               # single language
    python seed_qdrant.py --force                 # re-index even if .indexed exists
    python seed_qdrant.py --out-dir /some/path    # custom output dir
"""

import argparse
import json
import pathlib
import sys

import requests


# ---------------------------------------------------------------------------
# HTTP helpers — identical to pipeline.py
# ---------------------------------------------------------------------------

def _call_embed(server_url: str, segments: list) -> list:
    """POST /embed -> returns list of {text, ts_start, ts_end, vector}."""
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
    resp = requests.post(f"{server_url}/embed", json=payload, timeout=600)
    resp.raise_for_status()
    return resp.json()["vectors"]


def _call_index(server_url: str, video_id: str, file_path: str, lang: str, vectors: list) -> int:
    """POST /index -> returns indexed count."""
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Seed Qdrant from HPC pipeline output files."
    )
    parser.add_argument("--out-dir", default="sync/output",
                        help="Root folder containing {lang}/*.segments.json files (default: sync/output)")
    parser.add_argument("--lang", default=None,
                        help="Restrict to one language code")
    parser.add_argument("--embed-url", default="http://localhost:8765",
                        help="Embed server base URL (default: http://localhost:8765)")
    parser.add_argument("--index-url", default="http://localhost:8766",
                        help="Index server base URL (default: http://localhost:8766)")
    parser.add_argument("--force", action="store_true",
                        help="Re-index even if a .indexed sidecar exists")
    args = parser.parse_args()

    out_root = pathlib.Path(args.out_dir)
    if not out_root.is_dir():
        print(f"ERROR: output dir not found: {out_root}", file=sys.stderr)
        sys.exit(1)

    # Collect (segments_file, lang) pairs
    if args.lang:
        lang_dirs = [out_root / args.lang]
    else:
        lang_dirs = sorted(p for p in out_root.iterdir() if p.is_dir())

    pending = []
    for lang_dir in lang_dirs:
        lang = lang_dir.name
        for seg_file in sorted(lang_dir.glob("*.segments.json")):
            pending.append((seg_file, lang))

    if not pending:
        print("No *.segments.json files found.")
        return

    print(f"Embed URL  : {args.embed_url}")
    print(f"Index URL  : {args.index_url}")
    print(f"Files      : {len(pending)}\n")

    errors = 0

    for seg_file, lang in pending:
        stem = seg_file.name.replace(".segments.json", "")
        indexed_flag = seg_file.parent / f"{stem}.indexed"
        video_id = f"{lang}/{stem}"

        if indexed_flag.exists() and not args.force:
            print(f"[{lang}] {stem}  SKIP (already indexed)")
            continue

        print(f"[{lang}] {stem}")

        # Read segments
        try:
            segments = json.loads(seg_file.read_text())
        except Exception as exc:
            print(f"  ERROR reading segments: {exc}")
            errors += 1
            continue

        # Read optional sidecar files
        analysis_file = seg_file.parent / f"{stem}.analysis.json"
        sentiment_file = seg_file.parent / f"{stem}.sentiment.json"
        metadata = {}
        if analysis_file.exists():
            try:
                metadata.update(json.loads(analysis_file.read_text()))
            except Exception as exc:
                print(f"  WARN: could not read analysis: {exc}")
        if sentiment_file.exists():
            try:
                metadata.update(json.loads(sentiment_file.read_text()))
            except Exception as exc:
                print(f"  WARN: could not read sentiment: {exc}")

        # Embed + index
        try:
            vectors = _call_embed(args.embed_url, segments)
            n = _call_index(args.index_url, video_id, str(seg_file), lang, vectors)
            print(f"  indexed    -> {n} chunks")
        except Exception as exc:
            print(f"  EMBED/INDEX ERROR: {exc}")
            errors += 1
            continue

        # Metadata (optional — non-fatal)
        if metadata:
            try:
                _call_metadata(args.index_url, video_id, str(seg_file), lang, metadata)
                print(f"  metadata   -> ok")
            except Exception as exc:
                print(f"  METADATA WARN: {exc}")

        # Touch sidecar
        indexed_flag.touch()
        print(f"  done       -> {indexed_flag.name}")

    succeeded = len(pending) - errors
    print(f"\nFinished: {succeeded}/{len(pending)} succeeded, {errors} failed.")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
