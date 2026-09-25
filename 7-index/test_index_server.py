"""
Tests for index_server.py (7-index).

All external dependencies (QdrantClient) are mocked so no running Qdrant
instance is required.
"""

import json
import pytest
from unittest.mock import MagicMock

import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import index_server


SAMPLE_VECTORS = [
    {"text": "hello world", "ts_start": 0.0, "ts_end": 2.5, "vector": [0.1] * 1024},
    {"text": "foo bar",     "ts_start": 2.5, "ts_end": 5.0, "vector": [0.2] * 1024},
]


@pytest.fixture()
def client(monkeypatch):
    mock_qdrant = MagicMock()
    mock_qdrant.get_collection.return_value = True  # pretend collections exist
    monkeypatch.setattr(index_server, "_qdrant", mock_qdrant)
    index_server.app.config["TESTING"] = True
    with index_server.app.test_client() as c:
        yield c, mock_qdrant


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health_returns_ok(client):
    c, _ = client
    resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


# ---------------------------------------------------------------------------
# POST /index
# ---------------------------------------------------------------------------

def test_index_returns_indexed_count(client):
    c, _ = client
    body = {"video_id": "en/foo", "file": "inbox/en/foo.mp3", "lang": "en",
            "vectors": SAMPLE_VECTORS}
    resp = c.post("/index", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200
    assert resp.get_json()["indexed"] == len(SAMPLE_VECTORS)


def test_index_upserts_to_video_chunks_collection(client):
    c, mock_qdrant = client
    body = {"video_id": "en/foo", "file": "inbox/en/foo.mp3", "lang": "en",
            "vectors": SAMPLE_VECTORS}
    c.post("/index", data=json.dumps(body), content_type="application/json")
    mock_qdrant.upsert.assert_called_once()
    assert mock_qdrant.upsert.call_args[1]["collection_name"] == "video_chunks"


def test_index_point_payload_schema(client):
    c, mock_qdrant = client
    body = {"video_id": "en/foo", "file": "inbox/en/foo.mp3", "lang": "en",
            "vectors": [SAMPLE_VECTORS[0]]}
    c.post("/index", data=json.dumps(body), content_type="application/json")
    points = mock_qdrant.upsert.call_args[1]["points"]
    assert len(points) == 1
    payload = points[0].payload
    assert payload["video_id"] == "en/foo"
    assert payload["file"] == "inbox/en/foo.mp3"
    assert payload["lang"] == "en"
    assert payload["timestamp_start"] == 0.0
    assert payload["timestamp_end"] == 2.5
    assert payload["text"] == "hello world"


# ---------------------------------------------------------------------------
# POST /metadata
# ---------------------------------------------------------------------------

def test_metadata_upserts_to_video_metadata_collection(client):
    c, mock_qdrant = client
    body = {"video_id": "en/foo", "file": "inbox/en/foo.mp3", "lang": "en",
            "title": "My Video"}
    c.post("/metadata", data=json.dumps(body), content_type="application/json")
    mock_qdrant.upsert.assert_called_once()
    assert mock_qdrant.upsert.call_args[1]["collection_name"] == "video_metadata"


def test_metadata_returns_indexed_1(client):
    c, _ = client
    body = {"video_id": "en/foo", "file": "inbox/en/foo.mp3", "lang": "en"}
    resp = c.post("/metadata", data=json.dumps(body), content_type="application/json")
    assert resp.get_json()["indexed"] == 1


def test_metadata_preserves_payload_fields(client):
    c, mock_qdrant = client
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
    monkeypatch.setattr(index_server, "_qdrant", mock_qdrant)
    index_server._ensure_collections()
    assert mock_qdrant.create_collection.call_count == 2
    all_calls = [str(c) for c in mock_qdrant.create_collection.call_args_list]
    assert any("video_chunks" in s for s in all_calls)
    assert any("video_metadata" in s for s in all_calls)


def test_ensure_collections_skips_existing(monkeypatch):
    mock_qdrant = MagicMock()
    mock_qdrant.get_collection.return_value = True
    monkeypatch.setattr(index_server, "_qdrant", mock_qdrant)
    index_server._ensure_collections()
    mock_qdrant.create_collection.assert_not_called()
