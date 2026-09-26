"""
Personalised playlist generator — reads video_metadata from Qdrant and ranks
videos for a given user profile without running any additional model inference.

Ranking (personalised mode):
  1. Filter by user's language
  2. Exclude already-watched videos
  3. Score each candidate:
       role_score     = tag overlap with role tags from roles.yaml
       history_score  = tag overlap with tags from watched videos (implicit preference)
       sentiment_bonus= small boost for preferred sentiment
  4. Apply optional sentiment filter (--sentiment positive|neutral|negative)
  5. Return top-N as JSON

EU AI Act opt-out: --no-personalise (or "personalise": false in profile) returns
unranked results and does not read or record watch history.

Usage:
    python 9-graph/playlist.py --user engineer@org.com --top-n 10
    python 9-graph/playlist.py --user engineer@org.com --no-personalise
    python 9-graph/playlist.py --user engineer@org.com --sentiment positive --top-n 5
    python 9-graph/playlist.py --user engineer@org.com --qdrant-host localhost:6333
"""

import argparse
import json
import os
import sys

from typing import Optional

import yaml
from qdrant_client import QdrantClient

META_COLLECTION = "video_metadata"

# Paths relative to project root (one level up from this file's directory)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROLES_YAML = os.path.join(PROJECT_ROOT, "roles.yaml")
PROFILES_DIR = os.path.join(PROJECT_ROOT, "profiles")


def _parse_host_port(addr: str, default_port: int):
    if ":" in addr:
        host, port = addr.rsplit(":", 1)
        return host, int(port)
    return addr, default_port


def load_profile(user: str) -> dict:
    path = os.path.join(PROFILES_DIR, f"{user}.json")
    if not os.path.exists(path):
        print(f"ERROR: no profile found at {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_roles() -> dict:
    if not os.path.exists(ROLES_YAML):
        print(f"WARNING: {ROLES_YAML} not found — role boosting disabled.", file=sys.stderr)
        return {}
    with open(ROLES_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_all_metadata(qdrant: QdrantClient) -> list[dict]:
    records = []
    offset = None
    while True:
        result, next_offset = qdrant.scroll(
            collection_name=META_COLLECTION,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        records.extend(r.payload for r in result)
        if next_offset is None:
            break
        offset = next_offset
    return records


def _tag_set(record: dict) -> set:
    return set(record.get("tags") or [])


def score_candidates(
    candidates: list[dict],
    role_tags: set,
    history_tags: set,
    preferred_sentiment: Optional[str],
) -> list[dict]:
    """Score each candidate video; higher is better."""
    scored = []
    for rec in candidates:
        tags = _tag_set(rec)

        role_overlap = len(tags & role_tags)
        role_score = role_overlap / max(1, len(role_tags))

        history_overlap = len(tags & history_tags)
        history_score = history_overlap / max(1, len(history_tags)) if history_tags else 0.0

        sentiment_bonus = 0.0
        if preferred_sentiment and rec.get("sentiment_label") == preferred_sentiment:
            sentiment_bonus = 0.1

        total = 0.5 * role_score + 0.4 * history_score + sentiment_bonus

        scored.append({**rec, "_score": round(total, 4)})

    return sorted(scored, key=lambda r: r["_score"], reverse=True)


def format_result(rec: dict, rank: int, personalised: bool) -> dict:
    out = {
        "rank": rank,
        "file": rec.get("file", ""),
        "title": rec.get("title", ""),
        "lang": rec.get("lang", ""),
        "uploaded_by": rec.get("uploaded_by", ""),
        "tags": rec.get("tags", []),
        "sentiment_label": rec.get("sentiment_label", ""),
    }
    if personalised:
        out["score"] = rec.get("_score", 0.0)
    return out


def build_playlist(
    qdrant: QdrantClient,
    profile: dict,
    roles: dict,
    top_n: int,
    no_personalise: bool,
    sentiment_filter: Optional[str],
) -> list[dict]:
    personalised = not no_personalise and profile.get("personalise", True)

    all_records = load_all_metadata(qdrant)
    if not all_records:
        return []

    lang = profile.get("language", "")
    watched = set(profile.get("watched") or [])

    # Filter by language and exclude watched
    candidates = [
        r for r in all_records
        if (not lang or r.get("lang") == lang)
        and os.path.basename(r.get("file", "")) not in watched
        and r.get("file", "") not in watched
    ]

    # Optional sentiment filter
    if sentiment_filter:
        candidates = [r for r in candidates if r.get("sentiment_label") == sentiment_filter]

    if not personalised:
        # Unranked — alphabetical by file, no watch history used
        candidates.sort(key=lambda r: r.get("file", ""))
        return [format_result(r, i + 1, personalised=False) for i, r in enumerate(candidates[:top_n])]

    # Personalised ranking
    role = profile.get("role", "")
    role_tags = set(roles.get(role, []))

    # Derive history tags from watched video records (implicit preference signal)
    watched_records = [
        r for r in all_records
        if os.path.basename(r.get("file", "")) in watched
        or r.get("file", "") in watched
    ]
    history_tags: set = set()
    for wr in watched_records:
        history_tags |= _tag_set(wr)

    scored = score_candidates(candidates, role_tags, history_tags, preferred_sentiment=None)
    return [format_result(r, i + 1, personalised=True) for i, r in enumerate(scored[:top_n])]


def main():
    parser = argparse.ArgumentParser(description="Generate a personalised video playlist.")
    parser.add_argument("--user", required=True,
                        help="User identifier — must match a file in profiles/<user>.json")
    parser.add_argument("--top-n", type=int, default=10,
                        help="Number of results to return (default: 10)")
    parser.add_argument("--no-personalise", action="store_true",
                        help="Disable personalisation; return unranked results without reading watch history (EU AI Act opt-out)")
    parser.add_argument("--sentiment", choices=["positive", "neutral", "negative"], default=None,
                        help="Filter results to a specific sentiment label")
    parser.add_argument("--qdrant-host", default="localhost:6333",
                        help="Qdrant host:port (default: localhost:6333)")
    args = parser.parse_args()

    profile = load_profile(args.user)
    roles = load_roles()

    q_host, q_port = _parse_host_port(args.qdrant_host, 6333)
    qdrant = QdrantClient(host=q_host, port=q_port)

    try:
        playlist = build_playlist(
            qdrant=qdrant,
            profile=profile,
            roles=roles,
            top_n=args.top_n,
            no_personalise=args.no_personalise,
            sentiment_filter=args.sentiment,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(playlist, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
