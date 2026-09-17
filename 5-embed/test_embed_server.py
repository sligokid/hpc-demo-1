"""
Tests for embed-server.py.

All external dependencies (SentenceTransformer, QdrantClient) are mocked so
no model weights, GPU, or running Qdrant instance are required.
"""

import json
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

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

    mock_qdrant = MagicMock()
    mock_qdrant.get_collection.return_value = True  # pretend collections exist

    monkeypatch.setattr(embed_server, "_model", mock_model)
    monkeypatch.setattr(embed_server, "_qdrant", mock_qdrant)

    embed_server.app.config["TESTING"] = True
    with embed_server.app.test_client() as c:
        yield c, mock_model, mock_qdrant


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health_returns_ok(client):
    c, _, _ = client
    resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


# ---------------------------------------------------------------------------
# POST /embed
# ---------------------------------------------------------------------------

def test_embed_returns_indexed_count(client):
    c, _, _ = client
    body = {"video_id": "en/foo", "file": "inbox/en/foo.mp3", "lang": "en",
            "chunks": SAMPLE_CHUNKS}
    resp = c.post("/embed", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200
    assert resp.get_json()["indexed"] == len(SAMPLE_CHUNKS)


def test_embed_applies_passage_prefix(client):
    c, mock_model, _ = client
    body = {"video_id": "en/foo", "file": "inbox/en/foo.mp3", "lang": "en",
            "chunks": SAMPLE_CHUNKS}
    c.post("/embed", data=json.dumps(body), content_type="application/json")

    texts_encoded = mock_model.encode.call_args[0][0]
    for text, chunk in zip(texts_encoded, SAMPLE_CHUNKS):
        assert text == f"passage: {chunk['text']}"


def test_embed_upserts_to_video_chunks_collection(client):
    c, _, mock_qdrant = client
    body = {"video_id": "en/foo", "file": "inbox/en/foo.mp3", "lang": "en",
            "chunks": SAMPLE_CHUNKS}
    c.post("/embed", data=json.dumps(body), content_type="application/json")

    mock_qdrant.upsert.assert_called_once()
    call_kwargs = mock_qdrant.upsert.call_args[1]
    assert call_kwargs["collection_name"] == "video_chunks"


def test_embed_point_payload_schema(client):
    c, _, mock_qdrant = client
    body = {"video_id": "en/foo", "file": "inbox/en/foo.mp3", "lang": "en",
            "chunks": [SAMPLE_CHUNKS[0]]}
    c.post("/embed", data=json.dumps(body), content_type="application/json")

    points = mock_qdrant.upsert.call_args[1]["points"]
    assert len(points) == 1
    payload = points[0].payload
    assert payload["video_id"] == "en/foo"
    assert payload["file"] == "inbox/en/foo.mp3"
    assert payload["lang"] == "en"
    assert payload["timestamp_start"] == 0.0
    assert payload["timestamp_end"] == 2.5
    assert payload["text"] == "hello world"


def test_embed_normalise_embeddings_true(client):
    c, mock_model, _ = client
    body = {"video_id": "en/foo", "file": "inbox/en/foo.mp3", "lang": "en",
            "chunks": SAMPLE_CHUNKS}
    c.post("/embed", data=json.dumps(body), content_type="application/json")

    _, kwargs = mock_model.encode.call_args
    assert kwargs.get("normalize_embeddings") is True


# ---------------------------------------------------------------------------
# POST /metadata
# ---------------------------------------------------------------------------

def test_metadata_upserts_to_video_metadata_collection(client):
    c, _, mock_qdrant = client
    body = {"video_id": "en/foo", "file": "inbox/en/foo.mp3", "lang": "en",
            "title": "My Video"}
    c.post("/metadata", data=json.dumps(body), content_type="application/json")

    mock_qdrant.upsert.assert_called_once()
    call_kwargs = mock_qdrant.upsert.call_args[1]
    assert call_kwargs["collection_name"] == "video_metadata"


def test_metadata_returns_indexed_1(client):
    c, _, _ = client
    body = {"video_id": "en/foo", "file": "inbox/en/foo.mp3", "lang": "en"}
    resp = c.post("/metadata", data=json.dumps(body), content_type="application/json")
    assert resp.get_json()["indexed"] == 1


def test_metadata_preserves_payload_fields(client):
    c, _, mock_qdrant = client
    body = {"video_id": "en/foo", "file": "f.mp3", "lang": "en",
            "title": "Test", "tags": ["a", "b"]}
    c.post("/metadata", data=json.dumps(body), content_type="application/json")

    points = mock_qdrant.upsert.call_args[1]["points"]
    assert points[0].payload["title"] == "Test"
    assert points[0].payload["tags"] == ["a", "b"]


# ---------------------------------------------------------------------------
# _ensure_collections
# ---------------------------------------------------------------------------

def test_ensure_collections_creates_missing(monkeypatch):
    mock_qdrant = MagicMock()
    mock_qdrant.get_collection.side_effect = Exception("not found")
    monkeypatch.setattr(embed_server, "_qdrant", mock_qdrant)

    embed_server._ensure_collections()

    assert mock_qdrant.create_collection.call_count == 2
    all_calls = [str(c) for c in mock_qdrant.create_collection.call_args_list]
    assert any("video_chunks" in s for s in all_calls)
    assert any("video_metadata" in s for s in all_calls)


def test_ensure_collections_skips_existing(monkeypatch):
    mock_qdrant = MagicMock()
    mock_qdrant.get_collection.return_value = True  # no exception = exists
    monkeypatch.setattr(embed_server, "_qdrant", mock_qdrant)

    embed_server._ensure_collections()

    mock_qdrant.create_collection.assert_not_called()
