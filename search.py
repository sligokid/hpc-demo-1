"""
Semantic search over indexed video chunks in Qdrant.

Usage:
    python search.py --query "how to clear a jam on line 3"
    python search.py --query "..." --lang es --top-k 5
    python search.py --query "..." --qdrant-host localhost:6333
"""

import argparse
import json
from typing import Optional

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

EMBED_MODEL = "intfloat/multilingual-e5-large"
CHUNKS_COLLECTION = "video_chunks"


def _parse_host_port(addr: str, default_port: int):
    if ":" in addr:
        host, port = addr.rsplit(":", 1)
        return host, int(port)
    return addr, default_port


def search(query: str, lang: Optional[str], top_k: int, qdrant_host: str) -> list:
    q_host, q_port = _parse_host_port(qdrant_host, 6333)
    qdrant = QdrantClient(host=q_host, port=q_port)

    model = SentenceTransformer(EMBED_MODEL)
    vector = model.encode(f"query: {query}", normalize_embeddings=True).tolist()

    query_filter = None
    if lang:
        query_filter = Filter(
            must=[FieldCondition(key="lang", match=MatchValue(value=lang))]
        )

    response = qdrant.query_points(
        collection_name=CHUNKS_COLLECTION,
        query=vector,
        limit=top_k,
        query_filter=query_filter,
    )

    return [
        {
            "file": h.payload["file"],
            "timestamp_start": h.payload["timestamp_start"],
            "score": round(h.score, 4),
            "text": h.payload["text"],
        }
        for h in response.points
    ]


def main():
    parser = argparse.ArgumentParser(description="Search indexed video transcripts.")
    parser.add_argument("--query", required=True, help="Natural-language search query")
    parser.add_argument("--lang", default=None, help="Filter by language code (e.g. es)")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results (default: 5)")
    parser.add_argument("--qdrant-host", default="localhost:6333",
                        help="Qdrant host:port (default: localhost:6333)")
    args = parser.parse_args()

    results = search(args.query, args.lang, args.top_k, args.qdrant_host)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
