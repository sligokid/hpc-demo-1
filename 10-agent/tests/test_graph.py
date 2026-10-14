"""
Graph path tests for agent.py.
Runs headless with no live terminal. Qdrant, Ollama, and the embed model
are all mocked — no external services required.
"""

import json
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import (
    AgentState,
    build_graph,
    make_respond_node,
    make_run_tool_node,
    make_think_node,
    route_after_think,
    route_after_run_tool,
    _get_tool_calls,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_qdrant(search_results=None):
    """Return a fake QdrantClient whose query_points returns search_results."""
    qdrant = MagicMock()
    response = MagicMock()
    response.points = []
    if search_results:
        pts = []
        for r in search_results:
            pt = MagicMock()
            pt.payload = r
            pt.score = r.get("score", 0.9)
            pts.append(pt)
        response.points = pts
    qdrant.query_points.return_value = response
    qdrant.scroll.return_value = ([], None)
    return qdrant


def _mock_embed_model():
    model = MagicMock()
    vec = MagicMock()
    vec.tolist.return_value = [0.1] * 8
    model.encode.return_value = vec
    return model


def _ollama_tool_call_response(fn_name: str, fn_args: dict) -> dict:
    """Fake Ollama response that contains a single tool call."""
    return {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": fn_name,
                        "arguments": fn_args,
                    }
                }
            ],
        }
    }


def _ollama_final_response(content: str) -> dict:
    """Fake Ollama response that contains a plain-text answer (no tool calls)."""
    return {
        "message": {
            "role": "assistant",
            "content": content,
        }
    }


# ---------------------------------------------------------------------------
# route_after_think
# ---------------------------------------------------------------------------


def test_route_returns_run_tool_when_tool_calls_present():
    state = AgentState(
        messages=[
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "search_knowledge_base", "arguments": {}}}],
            }
        ],
        tool_results=[],
        answer="",
        sources=[],
    )
    assert route_after_think(state) == "run_tool"


def test_route_returns_respond_when_no_tool_calls():
    state = AgentState(
        messages=[{"role": "assistant", "content": "Here is the answer."}],
        tool_results=[],
        answer="",
        sources=[],
    )
    assert route_after_think(state) == "respond"


# ---------------------------------------------------------------------------
# think node
# ---------------------------------------------------------------------------


def test_think_appends_assistant_message():
    with patch("agent.requests.post") as mock_post:
        mock_post.return_value.json.return_value = _ollama_final_response("test answer")
        mock_post.return_value.raise_for_status = MagicMock()

        think = make_think_node("localhost:11434", "llama3")
        state = AgentState(
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": "hello"},
            ],
            tool_results=[],
            answer="",
            sources=[],
        )
        result = think(state)

    assert "messages" in result
    assert len(result["messages"]) == 1
    assert result["messages"][0]["role"] == "assistant"
    assert result["messages"][0]["content"] == "test answer"


# ---------------------------------------------------------------------------
# run_tool node
# ---------------------------------------------------------------------------


def test_run_tool_calls_search_knowledge_base():
    chunk = {
        "video_id": "en/foo",
        "file": "inbox/en/foo.mp3",
        "text": "hello world",
        "timestamp_start": 0.0,
        "timestamp_end": 2.5,
        "score": 0.95,
    }
    qdrant = _mock_qdrant(search_results=[chunk])
    embed = _mock_embed_model()

    run_tool = make_run_tool_node(qdrant, embed, "localhost:11434", "llama3")
    state = AgentState(
        messages=[
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "search_knowledge_base",
                            "arguments": {"query": "hello"},
                        }
                    }
                ],
            }
        ],
        tool_results=[],
        answer="",
        sources=[],
    )
    result = run_tool(state)

    assert len(result["messages"]) == 1
    assert result["messages"][0]["role"] == "tool"
    assert len(result["tool_results"]) == 1
    assert result["tool_results"][0]["video_id"] == "en/foo"


def test_run_tool_accumulates_tool_results():
    chunk = {
        "video_id": "en/bar",
        "file": "inbox/en/bar.mp3",
        "text": "another chunk",
        "timestamp_start": 1.0,
        "timestamp_end": 3.0,
        "score": 0.88,
    }
    qdrant = _mock_qdrant(search_results=[chunk])
    embed = _mock_embed_model()

    run_tool = make_run_tool_node(qdrant, embed, "localhost:11434", "llama3")
    existing_result = {
        "video_id": "en/prev",
        "file": "inbox/en/prev.mp3",
        "text": "previous",
        "timestamp_start": 0.0,
        "timestamp_end": 1.0,
        "score": 0.75,
    }
    state = AgentState(
        messages=[
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "search_knowledge_base",
                            "arguments": {"query": "another"},
                        }
                    }
                ],
            }
        ],
        tool_results=[existing_result],
        answer="",
        sources=[],
    )
    result = run_tool(state)

    assert len(result["tool_results"]) == 2
    assert result["tool_results"][0]["video_id"] == "en/prev"
    assert result["tool_results"][1]["video_id"] == "en/bar"


# ---------------------------------------------------------------------------
# respond node
# ---------------------------------------------------------------------------


def test_respond_sets_answer_and_sources():
    respond = make_respond_node()
    source = {
        "video_id": "en/foo",
        "file": "inbox/en/foo.mp3",
        "text": "hello",
        "timestamp_start": 0.0,
        "timestamp_end": 2.5,
        "score": 0.9,
    }
    state = AgentState(
        messages=[{"role": "assistant", "content": "The answer is 42."}],
        tool_results=[source],
        answer="",
        sources=[],
    )
    result = respond(state)

    assert result["answer"] == "The answer is 42."
    assert len(result["sources"]) == 1
    assert result["sources"][0]["video_id"] == "en/foo"


# ---------------------------------------------------------------------------
# Full graph path: think -> run_tool -> think -> respond
# ---------------------------------------------------------------------------


def test_graph_routes_think_run_tool_respond():
    """A question should traverse think->run_tool->think->respond without hitting
    any interrupt node. The final state must have a non-empty answer and sources."""

    chunk = {
        "video_id": "en/foo",
        "file": "inbox/en/foo.mp3",
        "text": "relevant content",
        "timestamp_start": 0.0,
        "timestamp_end": 2.5,
        "score": 0.92,
    }
    qdrant = _mock_qdrant(search_results=[chunk])
    embed = _mock_embed_model()

    call_count = 0

    def fake_post(url, json=None, timeout=None):
        nonlocal call_count
        call_count += 1
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        if call_count == 1:
            # First think: return a tool call
            mock_resp.json.return_value = _ollama_tool_call_response(
                "search_knowledge_base", {"query": "what is the topic?"}
            )
        else:
            # Second think: return a final answer
            mock_resp.json.return_value = _ollama_final_response(
                "The topic is relevant content."
            )
        return mock_resp

    with patch("agent.requests.post", side_effect=fake_post):
        graph = build_graph(qdrant, embed, "localhost:11434", "llama3")
        result = graph.invoke(
            {
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "What is the topic?"},
                ],
                "tool_results": [],
                "answer": "",
                "sources": [],
            }
        )

    assert result["answer"], "answer must be non-empty"
    assert len(result["sources"]) > 0, "sources must be non-empty"
    assert call_count == 2, "Ollama should have been called exactly twice (tool call + final answer)"


def test_graph_direct_respond_no_tool_call():
    """If the LLM answers immediately without calling a tool, the graph should
    route think -> respond directly. sources will be empty."""

    qdrant = _mock_qdrant()
    embed = _mock_embed_model()

    def fake_post(url, json=None, timeout=None):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _ollama_final_response("I don't know.")
        return mock_resp

    with patch("agent.requests.post", side_effect=fake_post):
        graph = build_graph(qdrant, embed, "localhost:11434", "llama3")
        result = graph.invoke(
            {
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Random question."},
                ],
                "tool_results": [],
                "answer": "",
                "sources": [],
            }
        )

    assert result["answer"] == "I don't know."
    assert result["sources"] == []
