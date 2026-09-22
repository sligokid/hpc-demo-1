"""
Consolidated tests for embed-server, sentiment, and label modules.

Covers:
  - chunk ingestion via POST /embed
  - Qdrant write (upsert called with correct collection and payload)
  - sentiment scoring (positive / negative / neutral)
  - JSONL label output
"""

import json
import numpy as np
import pathlib
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import embed_server
import sentiment as sent_mod
import label as label_mod


FAKE_VECTOR = np.ones(1024, dtype=np.float32)
SAMPLE_CHUNKS = [
    {"text": "hello world", "timestamp_start": 0.0, "timestamp_end": 2.5},
    {"text": "foo bar",     "timestamp_start": 2.5, "timestamp_end": 5.0},
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def embed_client(monkeypatch):
    mock_model = MagicMock()
    mock_model.encode.return_value = np.stack([FAKE_VECTOR] * 10)
    mock_qdrant = MagicMock()
    mock_qdrant.get_collection.return_value = True
    monkeypatch.setattr(embed_server, "_model", mock_model)
    monkeypatch.setattr(embed_server, "_qdrant", mock_qdrant)
    embed_server.app.config["TESTING"] = True
    with embed_server.app.test_client() as c:
        yield c, mock_model, mock_qdrant


@pytest.fixture(autouse=True)
def reset_sentiment_classifier():
    sent_mod._classifier = None
    yield
    sent_mod._classifier = None


# ---------------------------------------------------------------------------
# Chunk ingestion
# ---------------------------------------------------------------------------

def test_chunk_ingestion_returns_indexed_count(embed_client):
    c, _, _ = embed_client
    body = {"video_id": "en/foo", "file": "inbox/en/foo.mp3", "lang": "en",
            "chunks": SAMPLE_CHUNKS}
    resp = c.post("/embed", json=body)
    assert resp.status_code == 200
    assert resp.get_json()["indexed"] == len(SAMPLE_CHUNKS)


def test_chunk_ingestion_applies_passage_prefix(embed_client):
    c, mock_model, _ = embed_client
    body = {"video_id": "en/foo", "file": "inbox/en/foo.mp3", "lang": "en",
            "chunks": SAMPLE_CHUNKS}
    c.post("/embed", json=body)
    texts = mock_model.encode.call_args[0][0]
    for text, chunk in zip(texts, SAMPLE_CHUNKS):
        assert text == f"passage: {chunk['text']}"


# ---------------------------------------------------------------------------
# Qdrant write
# ---------------------------------------------------------------------------

def test_qdrant_write_targets_video_chunks_collection(embed_client):
    c, _, mock_qdrant = embed_client
    body = {"video_id": "en/foo", "file": "inbox/en/foo.mp3", "lang": "en",
            "chunks": SAMPLE_CHUNKS}
    c.post("/embed", json=body)
    mock_qdrant.upsert.assert_called_once()
    assert mock_qdrant.upsert.call_args[1]["collection_name"] == "video_chunks"


def test_qdrant_write_point_payload_fields(embed_client):
    c, _, mock_qdrant = embed_client
    body = {"video_id": "en/foo", "file": "inbox/en/foo.mp3", "lang": "en",
            "chunks": [SAMPLE_CHUNKS[0]]}
    c.post("/embed", json=body)
    payload = mock_qdrant.upsert.call_args[1]["points"][0].payload
    assert payload["video_id"] == "en/foo"
    assert payload["lang"] == "en"
    assert payload["timestamp_start"] == 0.0
    assert payload["text"] == "hello world"


# ---------------------------------------------------------------------------
# Sentiment scoring
# ---------------------------------------------------------------------------

def _make_clf(label, score):
    mock = MagicMock()
    mock.return_value = [[{"label": label, "score": score}]]
    return mock


def test_sentiment_positive_score_is_positive():
    with patch.object(sent_mod, "_get_classifier", return_value=_make_clf("positive", 0.9)):
        result = sent_mod.run_sentiment(["Great result!"])
    assert result["sentiment_label"] == "positive"
    assert result["sentiment_score"] > 0


def test_sentiment_negative_score_is_negative():
    with patch.object(sent_mod, "_get_classifier", return_value=_make_clf("negative", 0.8)):
        result = sent_mod.run_sentiment(["Terrible outcome."])
    assert result["sentiment_label"] == "negative"
    assert result["sentiment_score"] < 0


def test_sentiment_neutral_score_is_zero():
    with patch.object(sent_mod, "_get_classifier", return_value=_make_clf("neutral", 0.7)):
        result = sent_mod.run_sentiment(["The procedure has five steps."])
    assert result["sentiment_label"] == "neutral"
    assert result["sentiment_score"] == 0.0


# ---------------------------------------------------------------------------
# JSONL label output
# ---------------------------------------------------------------------------

def _mock_label_post(label="positive"):
    def _post(*args, **kwargs):
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"response": json.dumps({"label": label})}
        return resp
    return _post


def test_label_writes_jsonl_with_correct_fields(tmp_path):
    transcript = tmp_path / "test.transcript.txt"
    transcript.write_text("Great safety culture here. Everyone follows procedures.")
    labels_dir = tmp_path / "labels"
    labels_dir.mkdir()

    with patch("label.requests.post", side_effect=_mock_label_post("positive")):
        n = label_mod.label_transcript(transcript, "llama3", "localhost:11434", labels_dir)

    assert n >= 1
    out = labels_dir / "test.jsonl"
    assert out.exists()
    for line in out.read_text().strip().splitlines():
        record = json.loads(line)
        assert "chunk_text" in record
        assert record["label"] in label_mod.VALID_LABELS
        assert record["file"] == "test"


def test_label_jsonl_one_line_per_chunk(tmp_path):
    sentence = "This sentence has exactly ten words in it here. "
    transcript = tmp_path / "multi.transcript.txt"
    transcript.write_text(sentence * 60)
    labels_dir = tmp_path / "labels"
    labels_dir.mkdir()

    with patch("label.requests.post", side_effect=_mock_label_post("neutral")):
        n = label_mod.label_transcript(transcript, "llama3", "localhost:11434", labels_dir)

    lines = (labels_dir / "multi.jsonl").read_text().strip().splitlines()
    assert len(lines) == n
    assert n >= 3
