"""
Tests for search.py.

All external dependencies (SentenceTransformer, QdrantClient) are mocked so
no model weights, GPU, or running Qdrant instance are required.
"""

import numpy as np
from unittest.mock import MagicMock, patch

import search as search_mod  # alias avoids shadowing builtins


FAKE_VECTOR = np.ones(1024, dtype=np.float32)


def _make_response(hits):
    """Wrap a list of hits in an object with .points, matching query_points() return."""
    resp = MagicMock()
    resp.points = hits
    return resp


def _make_hit(file, ts_start, score, text):
    hit = MagicMock()
    hit.score = score
    hit.payload = {
        "file": file,
        "timestamp_start": ts_start,
        "text": text,
    }
    return hit


@patch("search.QdrantClient")
@patch("search.SentenceTransformer")
def test_query_applies_query_prefix(mock_st_cls, mock_qdrant_cls):
    mock_model = MagicMock()
    mock_model.encode.return_value = FAKE_VECTOR
    mock_st_cls.return_value = mock_model

    mock_qdrant = MagicMock()
    mock_qdrant.query_points.return_value = _make_response([])
    mock_qdrant_cls.return_value = mock_qdrant

    search_mod.search("triathlon", None, 5, "localhost:6333")

    encoded_text = mock_model.encode.call_args[0][0]
    assert encoded_text.startswith("query: ")
    assert "triathlon" in encoded_text


@patch("search.QdrantClient")
@patch("search.SentenceTransformer")
def test_normalise_embeddings_true(mock_st_cls, mock_qdrant_cls):
    mock_model = MagicMock()
    mock_model.encode.return_value = FAKE_VECTOR
    mock_st_cls.return_value = mock_model

    mock_qdrant = MagicMock()
    mock_qdrant.query_points.return_value = _make_response([])
    mock_qdrant_cls.return_value = mock_qdrant

    search_mod.search("triathlon", None, 5, "localhost:6333")

    _, kwargs = mock_model.encode.call_args
    assert kwargs.get("normalize_embeddings") is True


@patch("search.QdrantClient")
@patch("search.SentenceTransformer")
def test_lang_filter_applied_when_given(mock_st_cls, mock_qdrant_cls):
    mock_model = MagicMock()
    mock_model.encode.return_value = FAKE_VECTOR
    mock_st_cls.return_value = mock_model

    mock_qdrant = MagicMock()
    mock_qdrant.query_points.return_value = _make_response([])
    mock_qdrant_cls.return_value = mock_qdrant

    search_mod.search("triathlon", "es", 5, "localhost:6333")

    _, kwargs = mock_qdrant.query_points.call_args
    assert kwargs["query_filter"] is not None


@patch("search.QdrantClient")
@patch("search.SentenceTransformer")
def test_no_filter_when_lang_is_none(mock_st_cls, mock_qdrant_cls):
    mock_model = MagicMock()
    mock_model.encode.return_value = FAKE_VECTOR
    mock_st_cls.return_value = mock_model

    mock_qdrant = MagicMock()
    mock_qdrant.query_points.return_value = _make_response([])
    mock_qdrant_cls.return_value = mock_qdrant

    search_mod.search("triathlon", None, 5, "localhost:6333")

    _, kwargs = mock_qdrant.query_points.call_args
    assert kwargs["query_filter"] is None


@patch("search.QdrantClient")
@patch("search.SentenceTransformer")
def test_top_k_passed_to_qdrant(mock_st_cls, mock_qdrant_cls):
    mock_model = MagicMock()
    mock_model.encode.return_value = FAKE_VECTOR
    mock_st_cls.return_value = mock_model

    mock_qdrant = MagicMock()
    mock_qdrant.query_points.return_value = _make_response([])
    mock_qdrant_cls.return_value = mock_qdrant

    search_mod.search("triathlon", None, 7, "localhost:6333")

    _, kwargs = mock_qdrant.query_points.call_args
    assert kwargs["limit"] == 7


@patch("search.QdrantClient")
@patch("search.SentenceTransformer")
def test_result_schema(mock_st_cls, mock_qdrant_cls):
    mock_model = MagicMock()
    mock_model.encode.return_value = FAKE_VECTOR
    mock_st_cls.return_value = mock_model

    mock_qdrant = MagicMock()
    mock_qdrant.query_points.return_value = _make_response([
        _make_hit("inbox/en/foo.mp3", 12.5, 0.923, "hello world")
    ])
    mock_qdrant_cls.return_value = mock_qdrant

    results = search_mod.search("hello", None, 5, "localhost:6333")

    assert len(results) == 1
    r = results[0]
    assert r["file"] == "inbox/en/foo.mp3"
    assert r["timestamp_start"] == 12.5
    assert r["score"] == 0.923
    assert r["text"] == "hello world"


@patch("search.QdrantClient")
@patch("search.SentenceTransformer")
def test_searches_video_chunks_collection(mock_st_cls, mock_qdrant_cls):
    mock_model = MagicMock()
    mock_model.encode.return_value = FAKE_VECTOR
    mock_st_cls.return_value = mock_model

    mock_qdrant = MagicMock()
    mock_qdrant.query_points.return_value = _make_response([])
    mock_qdrant_cls.return_value = mock_qdrant

    search_mod.search("query", None, 5, "localhost:6333")

    _, kwargs = mock_qdrant.query_points.call_args
    assert kwargs["collection_name"] == "video_chunks"


@patch("search.QdrantClient")
@patch("search.SentenceTransformer")
def test_host_port_parsed_correctly(mock_st_cls, mock_qdrant_cls):
    mock_model = MagicMock()
    mock_model.encode.return_value = FAKE_VECTOR
    mock_st_cls.return_value = mock_model
    mock_qdrant = MagicMock()
    mock_qdrant.query_points.return_value = _make_response([])
    mock_qdrant_cls.return_value = mock_qdrant

    search_mod.search("query", None, 5, "qdrant-host:6399")

    _, kwargs = mock_qdrant_cls.call_args
    assert kwargs["host"] == "qdrant-host"
    assert kwargs["port"] == 6399
