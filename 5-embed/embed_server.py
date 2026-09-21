"""
Embedding server: loads intfloat/multilingual-e5-large once, accepts POST batches
of text chunks, and writes 1024-dim vectors to a local Qdrant instance.

Creates video_chunks (1024-dim cosine) and video_metadata (1-dim) collections on
startup if they do not already exist.

Usage:
    python 5-embed/embed_server.py
    python 5-embed/embed_server.py --qdrant-host localhost:6333 --port 8765

Endpoints:
    GET  /health              — liveness check
    POST /embed               — embed and index a batch of transcript chunks
    POST /metadata            — store per-file metadata in video_metadata
"""

import argparse
import uuid

from flask import Flask, request, jsonify
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

EMBED_MODEL = "intfloat/multilingual-e5-large"
VECTOR_DIM = 1024
CHUNKS_COLLECTION = "video_chunks"
META_COLLECTION = "video_metadata"

app = Flask(__name__)
_model: SentenceTransformer = None
_qdrant: QdrantClient = None


def _ensure_collections():
    for name, dim in ((CHUNKS_COLLECTION, VECTOR_DIM), (META_COLLECTION, 1)):
        try:
            _qdrant.get_collection(name)
        except Exception:
            _qdrant.create_collection(
                name,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
            print(f"  created collection: {name}")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/embed", methods=["POST"])
def embed():
    """
    Request body:
        {
            "video_id": "en/foo",
            "file": "inbox/en/foo.mp3",
            "lang": "en",
            "chunks": [{"text": "...", "timestamp_start": 0.0, "timestamp_end": 2.5}, ...]
        }
    Response: {"indexed": <count>}
    """
    body = request.get_json(force=True)
    video_id = body.get("video_id", "")
    file_path = body.get("file", "")
    lang = body.get("lang", "")
    chunks = body["chunks"]

    texts = [f"passage: {c['text']}" for c in chunks]
    vectors = _model.encode(texts, normalize_embeddings=True)

    # Deterministic IDs so reruns overwrite rather than duplicate.
    points = [
        PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{video_id}:{i}")),
            vector=vectors[i].tolist(),
            payload={
                "video_id": video_id,
                "file": file_path,
                "lang": lang,
                "timestamp_start": float(c["timestamp_start"]),
                "timestamp_end": float(c["timestamp_end"]),
                "text": c["text"],
            },
        )
        for i, c in enumerate(chunks)
    ]
    _qdrant.upsert(collection_name=CHUNKS_COLLECTION, points=points)
    return jsonify({"indexed": len(points)})


@app.route("/metadata", methods=["POST"])
def metadata():
    """
    Request body: any JSON dict (video_id, file, lang, title, description, tags, …)
    Response: {"indexed": 1}
    """
    body = request.get_json(force=True)
    # Deterministic ID keyed on video_id so reruns overwrite rather than duplicate.
    point = PointStruct(
        id=str(uuid.uuid5(uuid.NAMESPACE_URL, body.get("video_id", str(uuid.uuid4())))),
        vector=[0.0],
        payload=body,
    )
    _qdrant.upsert(collection_name=META_COLLECTION, points=[point])
    return jsonify({"indexed": 1})


def _parse_host_port(addr: str, default_port: int):
    if ":" in addr:
        host, port = addr.rsplit(":", 1)
        return host, int(port)
    return addr, default_port


def main():
    global _model, _qdrant

    parser = argparse.ArgumentParser()
    parser.add_argument("--qdrant-host", default="localhost:6333",
                        help="Qdrant host:port (default: localhost:6333)")
    parser.add_argument("--port", type=int, default=8765,
                        help="Port to listen on (default: 8765)")
    args = parser.parse_args()

    q_host, q_port = _parse_host_port(args.qdrant_host, 6333)
    _qdrant = QdrantClient(host=q_host, port=q_port)

    print(f"Loading model  : {EMBED_MODEL}")
    _model = SentenceTransformer(EMBED_MODEL)
    print(f"Model loaded.")

    _ensure_collections()
    print(f"Ready. Listening on :{args.port}")

    app.run(host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
