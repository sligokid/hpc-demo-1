"""
Read-only tool functions for the video knowledge-base agent.

All three functions are pure and stateless — Qdrant client and embed model
are injected as keyword arguments so they can be mocked in tests and swapped
at runtime.

Environment variables (with defaults):
    QDRANT_HOST   localhost:6333
    EMBED_MODEL   intfloat/multilingual-e5-large
"""

from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

CHUNKS_COLLECTION = "video_chunks"
META_COLLECTION = "video_metadata"


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
