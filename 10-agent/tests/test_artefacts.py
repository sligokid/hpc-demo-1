"""
Tests for the write-path tools (generate_summary, generate_playlist, save_artefact)
and the approval gate graph path (ask_approval with interrupt).

No live services required — Qdrant, Ollama, and the embed model are all mocked.
"""

import json
import os
import sys
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from agent import AgentState, build_graph
from tools import generate_playlist, generate_summary, save_artefact


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _mock_qdrant(search_points=None, scroll_payload=None):
    qdrant = MagicMock()

    # search_knowledge_base uses query_points
    response = MagicMock()
    pts = []
    for r in (search_points or []):
        pt = MagicMock()
        pt.payload = r
        pt.score = r.get("score", 0.9)
        pts.append(pt)
    response.points = pts
    qdrant.query_points.return_value = response

    # get_video_metadata and get_full_transcript use scroll
    if scroll_payload:
        rec = MagicMock()
        rec.payload = scroll_payload
        qdrant.scroll.return_value = ([rec], None)
    else:
        qdrant.scroll.return_value = ([], None)

    # save_artefact uses get_collections / create_collection / upsert
    collections_mock = MagicMock()
    collections_mock.collections = []
    qdrant.get_collections.return_value = collections_mock

    return qdrant


def _mock_embed():
    model = MagicMock()
    vec = MagicMock()
    vec.tolist.return_value = [0.1] * 8
    model.encode.return_value = vec
    return model


def _fake_ollama_response(content: str):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"message": {"content": content, "role": "assistant"}}
    return resp


def _fake_ollama_tool_call(fn_name: str, fn_args: dict):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_test01",
                    "function": {"name": fn_name, "arguments": fn_args},
                }
            ],
        }
    }
    return resp


# ---------------------------------------------------------------------------
# generate_summary
# ---------------------------------------------------------------------------


def test_generate_summary_returns_nonempty_string():
    chunks = [
        {"text": "Hello world.", "timestamp_start": 0.0, "timestamp_end": 2.0},
        {"text": "Second sentence.", "timestamp_start": 2.0, "timestamp_end": 4.0},
    ]
    rec = MagicMock()
    rec.payload = chunks[0]

    qdrant = MagicMock()
    # get_full_transcript scrolls until next_offset is None
    qdrant.scroll.side_effect = [
        ([MagicMock(payload=c) for c in chunks], None),
    ]

    with patch("tools.requests.post", return_value=_fake_ollama_response("## Summary\nGreat video.")):
        result = generate_summary(
            "en/foo",
            qdrant_client=qdrant,
            ollama_host="localhost:11434",
            model="llama3",
        )

    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_summary_no_transcript_returns_message():
    qdrant = MagicMock()
    qdrant.scroll.return_value = ([], None)

    result = generate_summary(
        "en/missing",
        qdrant_client=qdrant,
        ollama_host="localhost:11434",
        model="llama3",
    )

    assert "en/missing" in result
    assert "No transcript" in result


def test_generate_summary_sends_transcript_to_ollama():
    chunks = [{"text": "Content here.", "timestamp_start": 0.0, "timestamp_end": 2.0}]
    qdrant = MagicMock()
    qdrant.scroll.return_value = ([MagicMock(payload=c) for c in chunks], None)

    with patch("tools.requests.post", return_value=_fake_ollama_response("summary")) as mock_post:
        generate_summary("en/foo", qdrant_client=qdrant, ollama_host="localhost:11434", model="qwen2.5:3b")

    call_kwargs = mock_post.call_args[1]
    assert call_kwargs["json"]["model"] == "qwen2.5:3b"
    messages = call_kwargs["json"]["messages"]
    assert any("Content here." in str(m) for m in messages)


# ---------------------------------------------------------------------------
# generate_playlist
# ---------------------------------------------------------------------------


def test_generate_playlist_returns_list_with_required_fields():
    chunk = {
        "video_id": "en/foo",
        "file": "inbox/en/foo.mp3",
        "text": "intro",
        "timestamp_start": 0.0,
        "timestamp_end": 2.5,
        "score": 0.9,
    }
    meta = {"video_id": "en/foo", "title": "Foo Video", "lang": "en"}

    qdrant = MagicMock()
    response = MagicMock()
    pt = MagicMock()
    pt.payload = chunk
    pt.score = 0.9
    response.points = [pt]
    qdrant.query_points.return_value = response

    meta_rec = MagicMock()
    meta_rec.payload = meta
    qdrant.scroll.return_value = ([meta_rec], None)

    embed = _mock_embed()

    playlist_json = json.dumps([{
        "video_id": "en/foo",
        "title": "Foo Video",
        "timestamp_start": 0.0,
        "timestamp_end": 2.5,
        "reason": "Good introduction",
    }])

    with patch("tools.requests.post", return_value=_fake_ollama_response(playlist_json)):
        result = generate_playlist(
            "learn about foo",
            qdrant_client=qdrant,
            embed_model=embed,
            ollama_host="localhost:11434",
            model="llama3",
        )

    assert isinstance(result, list)
    assert len(result) >= 1
    required = {"video_id", "title", "timestamp_start", "timestamp_end", "reason"}
    assert required.issubset(set(result[0].keys()))


def test_generate_playlist_empty_search_returns_empty_list():
    qdrant = MagicMock()
    response = MagicMock()
    response.points = []
    qdrant.query_points.return_value = response
    qdrant.scroll.return_value = ([], None)
    embed = _mock_embed()

    result = generate_playlist(
        "nonexistent topic",
        qdrant_client=qdrant,
        embed_model=embed,
        ollama_host="localhost:11434",
        model="llama3",
    )

    assert result == []


# ---------------------------------------------------------------------------
# save_artefact
# ---------------------------------------------------------------------------


def test_save_artefact_writes_required_fields():
    qdrant = MagicMock()
    collections_mock = MagicMock()
    collections_mock.collections = []
    qdrant.get_collections.return_value = collections_mock

    artefact_id = save_artefact(
        "summary",
        "This is the content.",
        ["en/foo", "en/bar"],
        "testuser",
        qdrant_client=qdrant,
    )

    assert isinstance(artefact_id, str)
    assert len(artefact_id) == 36  # UUID format

    qdrant.upsert.assert_called_once()
    upsert_call = qdrant.upsert.call_args
    points = upsert_call[1]["points"]
    assert len(points) == 1
    payload = points[0].payload
    assert payload["type"] == "summary"
    assert payload["content"] == "This is the content."
    assert payload["approved_by"] == "testuser"
    assert "approved_at" in payload
    assert set(payload["source_video_ids"]) == {"en/foo", "en/bar"}


def test_save_artefact_creates_collection_if_missing():
    qdrant = MagicMock()
    collections_mock = MagicMock()
    collections_mock.collections = []
    qdrant.get_collections.return_value = collections_mock

    save_artefact("summary", "x", ["en/foo"], "user", qdrant_client=qdrant)

    qdrant.create_collection.assert_called_once()
    call_kwargs = qdrant.create_collection.call_args[1]
    assert call_kwargs["collection_name"] == "video_artefacts"


def test_save_artefact_skips_create_if_collection_exists():
    qdrant = MagicMock()
    existing = MagicMock()
    existing.name = "video_artefacts"
    collections_mock = MagicMock()
    collections_mock.collections = [existing]
    qdrant.get_collections.return_value = collections_mock

    save_artefact("summary", "x", ["en/foo"], "user", qdrant_client=qdrant)

    qdrant.create_collection.assert_not_called()


def test_save_artefact_deterministic_id():
    qdrant = MagicMock()
    collections_mock = MagicMock()
    collections_mock.collections = []
    qdrant.get_collections.return_value = collections_mock

    id1 = save_artefact("summary", "content a", ["en/foo"], "user", qdrant_client=qdrant)
    id2 = save_artefact("summary", "content b", ["en/foo"], "user", qdrant_client=qdrant)

    assert id1 == id2  # same type + same videos → same UUID (overwrite semantics)


# ---------------------------------------------------------------------------
# Graph path: write trigger → ask_approval interrupt
# ---------------------------------------------------------------------------


def _build_test_graph(qdrant, embed):
    return build_graph(
        qdrant, embed, "localhost:11434", "llama3", checkpointer=MemorySaver()
    )


def _run_with_interrupt(graph, initial_state, config):
    """Invoke graph, return (result, interrupted) tuple."""
    result = graph.invoke(initial_state, config=config)
    interrupted = bool(result.get("__interrupt__"))
    return result, interrupted


def test_graph_write_trigger_halts_at_approval_gate():
    """A generate_summary tool call should set pending_artefact and pause at
    ask_approval with __interrupt__ in the result."""
    chunks = [{"text": "video content", "timestamp_start": 0.0, "timestamp_end": 2.0}]
    qdrant = _mock_qdrant()
    qdrant.scroll.return_value = ([MagicMock(payload=c) for c in chunks], None)
    embed = _mock_embed()

    call_count = 0

    def fake_post(url, json=None, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # think: return generate_summary tool call
            return _fake_ollama_tool_call("generate_summary", {"video_id": "en/foo"})
        else:
            # generate_summary inside tools.py: return summary text
            return _fake_ollama_response("## Summary\nGreat video.")

    graph = _build_test_graph(qdrant, embed)
    config = {"configurable": {"thread_id": "test-interrupt-1"}}

    with patch("agent.requests.post", side_effect=fake_post), \
         patch("tools.requests.post", side_effect=fake_post):
        # Reset counter so patches share it properly
        call_count = 0
        result = graph.invoke(
            {
                "messages": [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "Summarise video en/foo"},
                ],
                "tool_results": [],
                "pending_artefact": None,
                "answer": "",
                "sources": [],
            },
            config=config,
        )

    assert result.get("__interrupt__"), "Graph should pause at ask_approval"
    assert "Draft Summary" in result["__interrupt__"][0].value or \
           "Summary" in result["__interrupt__"][0].value


def test_graph_reject_does_not_call_save_artefact():
    """Resuming with 'n' should discard the artefact — save_artefact not called."""
    chunks = [{"text": "content", "timestamp_start": 0.0, "timestamp_end": 2.0}]
    qdrant = _mock_qdrant()
    qdrant.scroll.return_value = ([MagicMock(payload=c) for c in chunks], None)
    embed = _mock_embed()

    call_count = 0

    def fake_post(url, json=None, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _fake_ollama_tool_call("generate_summary", {"video_id": "en/foo"})
        return _fake_ollama_response("## Summary\nContent.")

    graph = _build_test_graph(qdrant, embed)
    config = {"configurable": {"thread_id": "test-reject-1"}}
    initial = {
        "messages": [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "Summarise en/foo"},
        ],
        "tool_results": [],
        "pending_artefact": None,
        "answer": "",
        "sources": [],
    }

    with patch("agent.requests.post", side_effect=fake_post), \
         patch("tools.requests.post", side_effect=fake_post):
        call_count = 0
        result = graph.invoke(initial, config=config)
        assert result.get("__interrupt__"), "Should be interrupted"
        # Resume with rejection
        final = graph.invoke(Command(resume="n"), config=config)

    assert final["answer"] == "Artefact discarded."
    qdrant.upsert.assert_not_called()


def test_graph_approve_calls_save_artefact():
    """Resuming with 'y' should call save_artefact and record approved_by."""
    chunks = [{"text": "content", "timestamp_start": 0.0, "timestamp_end": 2.0}]
    qdrant = _mock_qdrant()
    qdrant.scroll.return_value = ([MagicMock(payload=c) for c in chunks], None)
    embed = _mock_embed()

    call_count = 0

    def fake_post(url, json=None, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _fake_ollama_tool_call("generate_summary", {"video_id": "en/foo"})
        return _fake_ollama_response("## Summary\nContent.")

    graph = _build_test_graph(qdrant, embed)
    config = {"configurable": {"thread_id": "test-approve-1"}}
    initial = {
        "messages": [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "Summarise en/foo"},
        ],
        "tool_results": [],
        "pending_artefact": None,
        "answer": "",
        "sources": [],
    }

    with patch("agent.requests.post", side_effect=fake_post), \
         patch("tools.requests.post", side_effect=fake_post), \
         patch("agent._get_username", return_value="testuser"):
        call_count = 0
        result = graph.invoke(initial, config=config)
        assert result.get("__interrupt__"), "Should be interrupted"
        final = graph.invoke(Command(resume="y"), config=config)

    qdrant.upsert.assert_called_once()
    upsert_payload = qdrant.upsert.call_args[1]["points"][0].payload
    assert upsert_payload["approved_by"] == "testuser"
    assert "approved_at" in upsert_payload
    assert "Saved summary" in final["answer"]
