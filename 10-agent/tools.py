"""
Tool functions for the video knowledge-base agent.

Read functions are pure and stateless — Qdrant client and embed model are
injected as keyword arguments so they can be mocked in tests and swapped at
runtime.

Write functions (generate_summary, generate_playlist, save_artefact) also
accept ollama_host / model as injected kwargs for the same reason.

Environment variables (with defaults):
    QDRANT_HOST   localhost:6333
    EMBED_MODEL   intfloat/multilingual-e5-large
"""

import datetime
import hashlib
import json
import re
import uuid
from typing import Optional

import requests
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)
from sentence_transformers import SentenceTransformer

CHUNKS_COLLECTION = "video_chunks"
META_COLLECTION = "video_metadata"
ARTEFACTS_COLLECTION = "video_artefacts"


def search_knowledge_base(
    query: str,
    lang: Optional[str] = None,
    top_k: int = 5,
    *,
    qdrant_client: QdrantClient,
    embed_model: SentenceTransformer,
) -> list:
    """Embed query and search video_chunks; return top_k results.

    Returns a list of dicts: {video_id, file, text, timestamp_start, timestamp_end, score}.
    Pass lang to restrict results to a single language code (e.g. "es").
    """
    vector = embed_model.encode(f"query: {query}", normalize_embeddings=True).tolist()

    query_filter = None
    if lang:
        query_filter = Filter(
            must=[FieldCondition(key="lang", match=MatchValue(value=lang))]
        )

    response = qdrant_client.query_points(
        collection_name=CHUNKS_COLLECTION,
        query=vector,
        limit=top_k,
        query_filter=query_filter,
    )

    return [
        {
            "video_id": h.payload["video_id"],
            "file": h.payload["file"],
            "text": h.payload["text"],
            "timestamp_start": h.payload["timestamp_start"],
            "timestamp_end": h.payload["timestamp_end"],
            "score": round(h.score, 4),
        }
        for h in response.points
    ]


def get_video_metadata(video_id: str, *, qdrant_client: QdrantClient) -> dict:
    """Fetch the full payload dict for a given video_id from video_metadata.

    Returns an empty dict when the video_id is not found.
    """
    results, _ = qdrant_client.scroll(
        collection_name=META_COLLECTION,
        scroll_filter=Filter(
            must=[FieldCondition(key="video_id", match=MatchValue(value=video_id))]
        ),
        limit=1,
        with_payload=True,
    )
    if not results:
        return {}
    return results[0].payload


def get_full_transcript(video_id: str, *, qdrant_client: QdrantClient) -> list:
    """Scroll all chunks for a video from video_chunks, ordered by timestamp_start.

    Returns a list of dicts: {text, timestamp_start, timestamp_end}.
    """
    chunks = []
    next_offset = None

    while True:
        batch, next_offset = qdrant_client.scroll(
            collection_name=CHUNKS_COLLECTION,
            scroll_filter=Filter(
                must=[FieldCondition(key="video_id", match=MatchValue(value=video_id))]
            ),
            limit=100,
            offset=next_offset,
            with_payload=True,
        )
        chunks.extend(batch)
        if next_offset is None:
            break

    return sorted(
        [
            {
                "text": c.payload["text"],
                "timestamp_start": c.payload["timestamp_start"],
                "timestamp_end": c.payload["timestamp_end"],
            }
            for c in chunks
        ],
        key=lambda x: x["timestamp_start"],
    )


def generate_summary(
    video_id: str,
    *,
    qdrant_client: QdrantClient,
    ollama_host: str,
    model: str,
) -> str:
    """Generate a structured summary of a video using its full transcript.

    Calls get_full_transcript, sends the result to Qwen via Ollama with a
    summarisation prompt, and returns the draft summary string.
    Does NOT persist anything.
    """
    from prompts import SUMMARISE_PROMPT  # avoid circular import at module level

    chunks = get_full_transcript(video_id, qdrant_client=qdrant_client)
    if not chunks:
        return f"No transcript found for video_id '{video_id}'."

    transcript = "\n".join(
        f"[{c['timestamp_start']:.1f}s] {c['text']}" for c in chunks
    )
    messages = [
        {"role": "system", "content": SUMMARISE_PROMPT},
        {"role": "user", "content": f"Video ID: {video_id}\n\nTranscript:\n{transcript}"},
    ]
    resp = requests.post(
        f"http://{ollama_host}/api/chat",
        json={"model": model, "messages": messages, "stream": False},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def generate_playlist(
    goal: str,
    *,
    qdrant_client: QdrantClient,
    embed_model: SentenceTransformer,
    ollama_host: str,
    model: str,
) -> list:
    """Generate an ordered playlist of videos for a learning or task goal.

    Runs multiple sub-queries via search_knowledge_base to get broad coverage,
    enriches results with metadata, then asks Qwen to order and reason over them.
    Returns a list of {video_id, title, timestamp_start, timestamp_end, reason}.
    Does NOT persist anything.
    """
    from prompts import PLAYLIST_PROMPT  # avoid circular import at module level

    # Multi-query search for broad coverage
    all_results: list = []
    for query in [goal, f"introduction to {goal}", f"{goal} overview"]:
        results = search_knowledge_base(
            query, top_k=5, qdrant_client=qdrant_client, embed_model=embed_model
        )
        all_results.extend(results)

    # Deduplicate by video_id, keep highest-scoring hit per video
    best: dict = {}
    for r in all_results:
        vid = r["video_id"]
        if vid not in best or r["score"] > best[vid]["score"]:
            best[vid] = r
    unique_results = list(best.values())

    if not unique_results:
        return []

    # Enrich with titles from metadata
    enriched = []
    for r in unique_results:
        meta = get_video_metadata(r["video_id"], qdrant_client=qdrant_client)
        title = meta.get("title") or meta.get("file") or r.get("file") or r["video_id"]
        enriched.append({**r, "title": title})

    messages = [
        {"role": "system", "content": PLAYLIST_PROMPT},
        {
            "role": "user",
            "content": f"Goal: {goal}\n\nAvailable videos:\n{json.dumps(enriched, indent=2)}",
        },
    ]
    resp = requests.post(
        f"http://{ollama_host}/api/chat",
        json={"model": model, "messages": messages, "stream": False},
        timeout=300,
    )
    resp.raise_for_status()
    content = resp.json()["message"]["content"]

    # Parse JSON array from the response; fall back to enriched results on failure
    try:
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            return json.loads(match.group())
        return json.loads(content)
    except (json.JSONDecodeError, AttributeError):
        return [
            {
                "video_id": r["video_id"],
                "title": r["title"],
                "timestamp_start": r["timestamp_start"],
                "timestamp_end": r["timestamp_end"],
                "reason": r["text"][:150],
            }
            for r in enriched[:5]
        ]


def save_artefact(
    type: str,
    content: str,
    video_ids: list,
    approved_by: str,
    *,
    qdrant_client: QdrantClient,
) -> str:
    """Persist an approved artefact to the video_artefacts Qdrant collection.

    Creates the collection automatically if it does not exist.
    Uses a deterministic UUID keyed on (type, sorted video_ids) so reruns
    overwrite rather than duplicate.

    Returns the artefact UUID string.
    """
    existing = {c.name for c in qdrant_client.get_collections().collections}
    if ARTEFACTS_COLLECTION not in existing:
        qdrant_client.create_collection(
            collection_name=ARTEFACTS_COLLECTION,
            vectors_config=VectorParams(size=1, distance=Distance.COSINE),
        )

    # Deterministic ID — same type + same videos always overwrites
    key = f"{type}:{'|'.join(sorted(video_ids))}"
    artefact_id = str(uuid.UUID(hashlib.md5(key.encode()).hexdigest()))

    qdrant_client.upsert(
        collection_name=ARTEFACTS_COLLECTION,
        points=[
            PointStruct(
                id=artefact_id,
                vector=[0.0],
                payload={
                    "type": type,
                    "content": content,
                    "source_video_ids": video_ids,
                    "approved_by": approved_by,
                    "approved_at": datetime.datetime.utcnow().isoformat() + "Z",
                },
            )
        ],
    )
    return artefact_id
