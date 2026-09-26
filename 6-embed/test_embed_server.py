"""
Tests for embed_server.py (6-embed).

Encoding only — no Qdrant dependency. SentenceTransformer is mocked so no
model weights or GPU are required.
"""

import json
import numpy as np
import pytest
from unittest.mock import MagicMock

import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import embed_server


FAKE_VECTOR = np.ones(1024, dtype=np.float32)

SAMPLE_CHUNKS = [
    {"text": "hello world", "timestamp_start": 0.0, "timestamp_end": 2.5},
    {"text": "foo bar",     "timestamp_start": 2.5, "timestamp_end": 5.0},
]


@pytest.fixture()
def client(monkeypatch):
    mock_model = MagicMock()
    mock_model.encode.return_value = np.stack([FAKE_VECTOR] * 10)
    monkeypatch.setattr(embed_server, "_model", mock_model)
    embed_server.app.config["TESTING"] = True
    with embed_server.app.test_client() as c:
        yield c, mock_model


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health_returns_ok(client):
    c, _ = client
    resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


# ---------------------------------------------------------------------------
# POST /embed
# ---------------------------------------------------------------------------

def test_embed_returns_vectors_key(client):
    c, _ = client
    resp = c.post("/embed", data=json.dumps({"chunks": SAMPLE_CHUNKS}),
                  content_type="application/json")
    assert resp.status_code == 200
    assert "vectors" in resp.get_json()


def test_embed_vectors_count_matches_chunks(client):
    c, _ = client
    resp = c.post("/embed", data=json.dumps({"chunks": SAMPLE_CHUNKS}),
                  content_type="application/json")
    assert len(resp.get_json()["vectors"]) == len(SAMPLE_CHUNKS)


def test_embed_vector_schema(client):
    c, _ = client
    resp = c.post("/embed", data=json.dumps({"chunks": [SAMPLE_CHUNKS[0]]}),
                  content_type="application/json")
    v = resp.get_json()["vectors"][0]
    assert v["text"] == "hello world"
    assert v["ts_start"] == 0.0
    assert v["ts_end"] == 2.5
    assert isinstance(v["vector"], list)
    assert len(v["vector"]) == 1024


def test_embed_applies_passage_prefix(client):
    c, mock_model = client
    c.post("/embed", data=json.dumps({"chunks": SAMPLE_CHUNKS}),
           content_type="application/json")
    texts_encoded = mock_model.encode.call_args[0][0]
    for text, chunk in zip(texts_encoded, SAMPLE_CHUNKS):
        assert text == f"passage: {chunk['text']}"


def test_embed_normalise_embeddings_true(client):
    c, mock_model = client
    c.post("/embed", data=json.dumps({"chunks": SAMPLE_CHUNKS}),
           content_type="application/json")
    _, kwargs = mock_model.encode.call_args
    assert kwargs.get("normalize_embeddings") is True
