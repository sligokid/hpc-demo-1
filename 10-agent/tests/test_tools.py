"""
Tests for tools.py — all three read functions mocked against a fake Qdrant client.
No live Qdrant connection required.
"""

import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools import search_knowledge_base, get_video_metadata, get_full_transcript


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _point(payload, score=0.9):
    pt = MagicMock()
    pt.payload = payload
    pt.score = score
    return pt


def _record(payload):
    rec = MagicMock()
    rec.payload = payload
    return rec


def _embed_model(dim=8):
    model = MagicMock()
    vec = MagicMock()
    vec.tolist.return_value = [0.1] * dim
    model.encode.return_value = vec
    return model


# ---------------------------------------------------------------------------
# search_knowledge_base
# ---------------------------------------------------------------------------

def test_search_knowledge_base_result_shape():
    payload = {
        "video_id": "en/foo",
        "file": "inbox/en/foo.mp3",
        "text": "hello world",
        "timestamp_start": 0.0,
        "timestamp_end": 2.5,
    }
    response = MagicMock()
    response.points = [_point(payload, score=0.9512)]

    qdrant = MagicMock()
    qdrant.query_points.return_value = response

    results = search_knowledge_base(
        "hello", qdrant_client=qdrant, embed_model=_embed_model()
    )

    assert len(results) == 1
    r = results[0]
    assert set(r.keys()) == {"video_id", "file", "text", "timestamp_start", "timestamp_end", "score"}
    assert r["video_id"] == "en/foo"
    assert r["text"] == "hello world"
    assert r["timestamp_start"] == 0.0
    assert r["timestamp_end"] == 2.5
    assert r["score"] == 0.9512


def test_search_knowledge_base_uses_query_prefix():
    response = MagicMock()
    response.points = []
    qdrant = MagicMock()
    qdrant.query_points.return_value = response
    model = _embed_model()

    search_knowledge_base("machine safety", qdrant_client=qdrant, embed_model=model)

    encoded_text = model.encode.call_args[0][0]
    assert encoded_text == "query: machine safety"


def test_search_knowledge_base_queries_video_chunks():
    response = MagicMock()
    response.points = []
    qdrant = MagicMock()
    qdrant.query_points.return_value = response

    search_knowledge_base("test", qdrant_client=qdrant, embed_model=_embed_model())

    call_kwargs = qdrant.query_points.call_args[1]
    assert call_kwargs["collection_name"] == "video_chunks"


def test_search_knowledge_base_lang_filter():
    response = MagicMock()
    response.points = []
    qdrant = MagicMock()
    qdrant.query_points.return_value = response

    search_knowledge_base("test", lang="es", qdrant_client=qdrant, embed_model=_embed_model())

    call_kwargs = qdrant.query_points.call_args[1]
    assert call_kwargs["query_filter"] is not None


def test_search_knowledge_base_no_lang_filter():
    response = MagicMock()
    response.points = []
    qdrant = MagicMock()
    qdrant.query_points.return_value = response

    search_knowledge_base("test", lang=None, qdrant_client=qdrant, embed_model=_embed_model())

    call_kwargs = qdrant.query_points.call_args[1]
    assert call_kwargs["query_filter"] is None


# ---------------------------------------------------------------------------
# get_video_metadata
# ---------------------------------------------------------------------------

def test_get_video_metadata_returns_payload():
    payload = {"video_id": "en/foo", "file": "inbox/en/foo.mp3", "title": "Foo", "lang": "en"}
    qdrant = MagicMock()
    qdrant.scroll.return_value = ([_record(payload)], None)

    result = get_video_metadata("en/foo", qdrant_client=qdrant)

    assert result == payload


def test_get_video_metadata_queries_video_metadata():
    qdrant = MagicMock()
    qdrant.scroll.return_value = ([], None)

    get_video_metadata("en/foo", qdrant_client=qdrant)

    call_kwargs = qdrant.scroll.call_args[1]
    assert call_kwargs["collection_name"] == "video_metadata"


def test_get_video_metadata_not_found_returns_empty():
    qdrant = MagicMock()
    qdrant.scroll.return_value = ([], None)

    result = get_video_metadata("missing/video", qdrant_client=qdrant)

    assert result == {}


# ---------------------------------------------------------------------------
# get_full_transcript
# ---------------------------------------------------------------------------

def test_get_full_transcript_ordered_by_timestamp():
    chunks_data = [
        {"text": "third", "timestamp_start": 5.0, "timestamp_end": 7.5},
        {"text": "first", "timestamp_start": 0.0, "timestamp_end": 2.5},
        {"text": "second", "timestamp_start": 2.5, "timestamp_end": 5.0},
    ]
    qdrant = MagicMock()
    qdrant.scroll.return_value = ([_record(c) for c in chunks_data], None)

    result = get_full_transcript("en/foo", qdrant_client=qdrant)

    assert len(result) == 3
    assert result[0]["timestamp_start"] == 0.0
    assert result[1]["timestamp_start"] == 2.5
    assert result[2]["timestamp_start"] == 5.0


def test_get_full_transcript_result_shape():
    chunk = {"text": "hello", "timestamp_start": 0.0, "timestamp_end": 2.5}
    qdrant = MagicMock()
    qdrant.scroll.return_value = ([_record(chunk)], None)

    result = get_full_transcript("en/foo", qdrant_client=qdrant)

    assert set(result[0].keys()) == {"text", "timestamp_start", "timestamp_end"}


def test_get_full_transcript_queries_video_chunks():
    qdrant = MagicMock()
    qdrant.scroll.return_value = ([], None)

    get_full_transcript("en/foo", qdrant_client=qdrant)

    call_kwargs = qdrant.scroll.call_args[1]
    assert call_kwargs["collection_name"] == "video_chunks"
