"""
Embedding server: loads intfloat/multilingual-e5-large once, accepts POST batches
of text chunks, and returns 1024-dim vectors. No Qdrant dependency.

Usage:
    python 6-embed/embed_server.py
    python 6-embed/embed_server.py --port 8765

Endpoints:
    GET  /health              — liveness check
    POST /embed               — encode a batch of transcript chunks; returns raw vectors
"""

import argparse

from flask import Flask, request, jsonify
from sentence_transformers import SentenceTransformer

EMBED_MODEL = "intfloat/multilingual-e5-large"

app = Flask(__name__)
_model: SentenceTransformer = None


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/embed", methods=["POST"])
def embed():
    """
    Request body:
        {
            "chunks": [{"text": "...", "timestamp_start": 0.0, "timestamp_end": 2.5}, ...]
        }
    Response:
        {"vectors": [{"text": "...", "ts_start": 0.0, "ts_end": 2.5, "vector": [...]}, ...]}
    """
    body = request.get_json(force=True)
    chunks = body["chunks"]

    texts = [f"passage: {c['text']}" for c in chunks]
    vectors = _model.encode(texts, normalize_embeddings=True)

    return jsonify({
        "vectors": [
            {
                "text": c["text"],
                "ts_start": float(c["timestamp_start"]),
                "ts_end": float(c["timestamp_end"]),
                "vector": vectors[i].tolist(),
            }
            for i, c in enumerate(chunks)
        ]
    })


def main():
    global _model

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765,
                        help="Port to listen on (default: 8765)")
    args = parser.parse_args()

    print(f"Loading model  : {EMBED_MODEL}")
    _model = SentenceTransformer(EMBED_MODEL)
    print(f"Model loaded.")
    print(f"Ready. Listening on :{args.port}")

    app.run(host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
