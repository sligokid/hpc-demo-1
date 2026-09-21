"""
Tests for label.py.

Ollama HTTP calls are mocked so no running Ollama instance is required.
"""

import json
import pathlib
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import label as label_mod


# ---------------------------------------------------------------------------
# _split_text (shared logic, same as sentiment._split_text)
# ---------------------------------------------------------------------------

def test_split_text_returns_list():
    chunks = label_mod._split_text("Hello world.")
    assert isinstance(chunks, list)
    assert len(chunks) >= 1


def test_split_text_long_text_splits():
    sentence = "Each sentence has exactly ten words in total here. "
    text = sentence * 60
    chunks = label_mod._split_text(text)
    assert len(chunks) >= 3


# ---------------------------------------------------------------------------
# _call_ollama
# ---------------------------------------------------------------------------

def _mock_response(label: str, status: int = 200):
    resp = MagicMock()
    resp.ok = status == 200
    resp.status_code = status
    resp.json.return_value = {"response": json.dumps({"label": label})}
    return resp


def test_call_ollama_returns_valid_label():
    with patch("label.requests.post", return_value=_mock_response("positive")):
        result = label_mod._call_ollama("Great job!", "llama3", "localhost:11434")
    assert result == "positive"


def test_call_ollama_negative_label():
    with patch("label.requests.post", return_value=_mock_response("negative")):
        result = label_mod._call_ollama("Safety hazard detected.", "llama3", "localhost:11434")
    assert result == "negative"


def test_call_ollama_neutral_label():
    with patch("label.requests.post", return_value=_mock_response("neutral")):
        result = label_mod._call_ollama("The procedure has five steps.", "llama3", "localhost:11434")
    assert result == "neutral"


def test_call_ollama_falls_back_to_neutral_on_invalid_json():
    resp = MagicMock()
    resp.ok = True
    resp.json.return_value = {"response": "not valid json {{"}
    with patch("label.requests.post", return_value=resp):
        result = label_mod._call_ollama("Some text.", "llama3", "localhost:11434")
    assert result == "neutral"


def test_call_ollama_falls_back_to_neutral_on_unknown_label():
    resp = MagicMock()
    resp.ok = True
    resp.json.return_value = {"response": json.dumps({"label": "strongly_positive"})}
    with patch("label.requests.post", return_value=resp):
        result = label_mod._call_ollama("Great!", "llama3", "localhost:11434")
    assert result == "neutral"


# ---------------------------------------------------------------------------
# label_transcript
# ---------------------------------------------------------------------------

def test_label_transcript_writes_jsonl(tmp_path):
    transcript = tmp_path / "foo.transcript.txt"
    transcript.write_text(
        "Great safety culture here. Everyone follows the procedures. "
        "Training was excellent and well-received by the team."
    )
    labels_dir = tmp_path / "labels"
    labels_dir.mkdir()

    with patch("label.requests.post", return_value=_mock_response("positive")):
        n = label_mod.label_transcript(transcript, "llama3", "localhost:11434", labels_dir)

    assert n >= 1
    out = labels_dir / "foo.jsonl"
    assert out.exists()
    lines = out.read_text().strip().splitlines()
    assert len(lines) == n
    for line in lines:
        record = json.loads(line)
        assert "chunk_text" in record
        assert record["label"] in label_mod.VALID_LABELS
        assert record["file"] == "foo"


def test_label_transcript_empty_file_returns_zero(tmp_path):
    transcript = tmp_path / "empty.transcript.txt"
    transcript.write_text("   ")
    labels_dir = tmp_path / "labels"
    labels_dir.mkdir()

    n = label_mod.label_transcript(transcript, "llama3", "localhost:11434", labels_dir)
    assert n == 0


def test_label_transcript_jsonl_one_line_per_chunk(tmp_path):
    # Build a ~600-word transcript to guarantee multiple chunks
    sentence = "This sentence contains exactly ten words total here okay. "
    transcript = tmp_path / "multi.transcript.txt"
    transcript.write_text(sentence * 60)
    labels_dir = tmp_path / "labels"
    labels_dir.mkdir()

    with patch("label.requests.post", return_value=_mock_response("neutral")):
        n = label_mod.label_transcript(transcript, "llama3", "localhost:11434", labels_dir)

    out = labels_dir / "multi.jsonl"
    lines = out.read_text().strip().splitlines()
    assert len(lines) == n
    assert n >= 3
