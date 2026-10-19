"""
LangGraph agent for the video knowledge-base RAG chat.

Graph topology (read path):
    think -> run_tool -> think  (cycles until LLM has enough info)
    think -> respond            (when LLM returns a plain-text answer)

Graph topology (write path):
    think -> run_tool -> ask_approval -> END
    (run_tool sets pending_artefact; ask_approval interrupts for y/n)

The graph is importable and testable without a live terminal — all external
dependencies (Qdrant, Ollama, SentenceTransformer) are injected via
build_graph() so they can be mocked in tests.
"""

import json
import os
import sys
import uuid
from typing import Annotated, Any, List, Literal, Optional

import requests
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from typing_extensions import TypedDict

from prompts import SYSTEM_PROMPT
from tools import (
    generate_playlist,
    generate_summary,
    get_full_transcript,
    get_video_metadata,
    save_artefact,
    search_knowledge_base,
)

# ---------------------------------------------------------------------------
# Tool schema (Ollama tool-calling format)
# ---------------------------------------------------------------------------

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": (
                "Embed a natural-language query and search the video transcript knowledge base. "
                "Returns the top matching text chunks with timestamps and scores. "
                "Use this first for any factual question."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query in natural language.",
                    },
                    "lang": {
                        "type": "string",
                        "description": (
                            "Optional ISO language code to restrict results "
                            "(en, es, fr, zh, ar). Omit to search across all languages."
                        ),
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default 5).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_video_metadata",
            "description": (
                "Retrieve full metadata (title, description, creator, lang) for a video "
                "by its video_id. Call this after search_knowledge_base when you need the "
                "video title or creator."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "video_id": {
                        "type": "string",
                        "description": "The video_id returned by search_knowledge_base.",
                    }
                },
                "required": ["video_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_full_transcript",
            "description": (
                "Fetch the complete ordered transcript for a video. "
                "Only use this when the user explicitly requests the full transcript."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "video_id": {
                        "type": "string",
                        "description": "The video_id to fetch the full transcript for.",
                    }
                },
                "required": ["video_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_summary",
            "description": (
                "Generate a structured summary of a video from its full transcript. "
                "Use this when the user asks to summarise a specific video. "
                "The draft will be shown for approval before being saved."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "video_id": {
                        "type": "string",
                        "description": "The video_id to summarise.",
                    }
                },
                "required": ["video_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_playlist",
            "description": (
                "Generate an ordered playlist of videos for a learning or task goal. "
                "ALWAYS call this tool when the user asks for a playlist or confirms they want one. "
                "Never write a playlist as text — always call this tool. "
                "The draft will be shown for approval before being saved."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "The learning goal or topic for the playlist.",
                    }
                },
                "required": ["goal"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    tool_results: list          # accumulated search results for the sources block
    pending_artefact: Optional[dict]  # set by run_tool when a draft is ready
    answer: str                 # set by respond or ask_approval
    sources: list               # set by respond or ask_approval


# ---------------------------------------------------------------------------
# Ollama helpers
# ---------------------------------------------------------------------------

# LangChain's add_messages reducer converts plain dicts to typed message objects
# (SystemMessage, HumanMessage, AIMessage, ToolMessage). We must convert them
# back to plain dicts before POSTing to Ollama, which expects a JSON-serialisable
# list of {"role": ..., "content": ...} dicts.

_LANGCHAIN_ROLE = {
    "system": "system",
    "human": "user",
    "ai": "assistant",
    "tool": "tool",
}


def _serialize_messages(messages: list) -> list:
    """Convert LangChain message objects (or plain dicts) to Ollama-format dicts."""
    result = []
    for msg in messages:
        if isinstance(msg, dict):
            result.append(msg)
            continue
        role = _LANGCHAIN_ROLE.get(msg.type, msg.type)
        d: dict = {"role": role, "content": msg.content or ""}

        # AIMessage: convert LangChain tool_calls back to Ollama function format
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            d["tool_calls"] = []
            for tc in tool_calls:
                if isinstance(tc, dict):
                    name = tc.get("name", "")
                    args = tc.get("args", {})
                    call_id = tc.get("id", "")
                else:
                    name = tc.name
                    args = tc.args
                    call_id = getattr(tc, "id", "") or ""
                d["tool_calls"].append(
                    {"id": call_id, "function": {"name": name, "arguments": args}}
                )

        # Note: Ollama does not use tool_call_id on tool result messages,
        # so we intentionally omit it from the serialised output.

        result.append(d)
    return result


def _ollama_chat(
    messages: list,
    *,
    ollama_host: str,
    model: str,
    tools: Optional[List] = None,
) -> dict:
    """POST to Ollama /api/chat and return the parsed response dict."""
    url = f"http://{ollama_host}/api/chat"
    payload: dict[str, Any] = {
        "model": model,
        "messages": _serialize_messages(messages),
        "stream": False,
        "options": {"temperature": 0},
    }
    if tools:
        payload["tools"] = tools
    resp = requests.post(url, json=payload, timeout=300)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


def make_think_node(ollama_host: str, model: str):
    def think(state: AgentState) -> dict:
        response = _ollama_chat(
            state["messages"],
            ollama_host=ollama_host,
            model=model,
            tools=TOOLS_SCHEMA,
        )
        msg = response["message"]
        # LangChain's message converter requires an 'id' on each tool call;
        # Ollama doesn't include one, so we add a generated id.
        for tc in msg.get("tool_calls") or []:
            if isinstance(tc, dict) and "id" not in tc:
                tc["id"] = f"call_{uuid.uuid4().hex[:8]}"
        return {"messages": [msg]}

    return think


def make_run_tool_node(
    qdrant_client: QdrantClient,
    embed_model: SentenceTransformer,
    ollama_host: str,
    generate_model: str,
):
    def run_tool(state: AgentState) -> dict:
        last = state["messages"][-1]
        tool_calls = _get_tool_calls(last)

        tool_messages = []
        new_results: list = []
        pending: Optional[dict] = None

        for tc in tool_calls:
            fn_name, fn_args, call_id = _parse_tool_call(tc)

            if fn_name == "search_knowledge_base":
                result = search_knowledge_base(
                    fn_args["query"],
                    lang=fn_args.get("lang"),
                    top_k=fn_args.get("top_k", 5),
                    qdrant_client=qdrant_client,
                    embed_model=embed_model,
                )
                new_results.extend(result)
                content = json.dumps(result)
            elif fn_name == "get_video_metadata":
                result = get_video_metadata(
                    fn_args["video_id"], qdrant_client=qdrant_client
                )
                content = json.dumps(result)
            elif fn_name == "get_full_transcript":
                result = get_full_transcript(
                    fn_args["video_id"], qdrant_client=qdrant_client
                )
                content = json.dumps(result)
            elif fn_name == "generate_summary":
                summary = generate_summary(
                    fn_args["video_id"],
                    qdrant_client=qdrant_client,
                    ollama_host=ollama_host,
                    model=generate_model,
                )
                pending = {
                    "type": "summary",
                    "content": summary,
                    "video_ids": [fn_args["video_id"]],
                }
                content = summary
            elif fn_name == "generate_playlist":
                playlist = generate_playlist(
                    fn_args["goal"],
                    qdrant_client=qdrant_client,
                    embed_model=embed_model,
                    ollama_host=ollama_host,
                    model=generate_model,
                )
                pending = {
                    "type": "playlist",
                    "content": json.dumps(playlist, indent=2),
                    "video_ids": [item["video_id"] for item in playlist],
                }
                content = json.dumps(playlist)
            else:
                content = json.dumps({"error": f"Unknown tool: {fn_name}"})

            tool_messages.append(
                {"role": "tool", "content": content, "tool_call_id": call_id}
            )

        existing = list(state.get("tool_results") or [])
        return {
            "messages": tool_messages,
            "tool_results": existing + new_results,
            "pending_artefact": pending,
        }

    return run_tool


def make_respond_node():
    def respond(state: AgentState) -> dict:
        last = state["messages"][-1]
        answer_text = _get_content(last)
        sources = list(state.get("tool_results") or [])
        return {"answer": answer_text, "sources": sources}

    return respond


# ---------------------------------------------------------------------------
# Message helpers (handle both LangChain message objects and plain dicts)
# ---------------------------------------------------------------------------


def _get_tool_calls(msg) -> list:
    """Return tool_calls list from either a LangChain message object or a plain dict."""
    if isinstance(msg, dict):
        return msg.get("tool_calls") or []
    return getattr(msg, "tool_calls", None) or []


def _get_content(msg) -> str:
    """Return content string from either a LangChain message object or a plain dict."""
    if isinstance(msg, dict):
        return msg.get("content", "") or ""
    return getattr(msg, "content", "") or ""


def _parse_tool_call(tc) -> tuple:
    """Return (fn_name, fn_args, call_id) from a tool call in any supported format.

    Supported formats:
      - Ollama raw dict: {"function": {"name": ..., "arguments": ...}, "id": ...}
      - LangChain dict:  {"name": ..., "args": ..., "id": ...}
      - LangChain object with .name, .args, and .id attributes
    """
    if isinstance(tc, dict):
        if "function" in tc:
            fn_name = tc["function"]["name"]
            fn_args = tc["function"]["arguments"]
            call_id = tc.get("id", "")
        else:
            fn_name = tc["name"]
            fn_args = tc.get("args", {})
            call_id = tc.get("id", "")
    else:
        fn_name = tc.name
        fn_args = tc.args
        call_id = getattr(tc, "id", "") or ""

    if isinstance(fn_args, str):
        fn_args = json.loads(fn_args)
    return fn_name, fn_args, call_id


# ---------------------------------------------------------------------------
# Approval gate node
# ---------------------------------------------------------------------------


def _get_username() -> str:
    try:
        return os.getlogin()
    except OSError:
        return os.environ.get("USER", os.environ.get("USERNAME", "unknown"))


def _format_artefact_display(artefact: dict) -> str:
    sep = "=" * 52
    lines = [
        "",
        sep,
        f"  Draft {artefact['type'].title()}",
        sep,
        artefact["content"],
        sep,
        f"  Source videos: {', '.join(artefact['video_ids'])}",
        sep,
    ]
    return "\n".join(lines)


def make_ask_approval_node(qdrant_client: QdrantClient):
    """Return the ask_approval node.

    Uses LangGraph interrupt() to pause and surface the draft artefact to the
    CLI. On resume:
      - "y" / "yes"  → saves via save_artefact, records approver identity
      - anything else → discards silently

    save_artefact is NOT in TOOLS_SCHEMA and is only reachable via this node.
    """

    def ask_approval(state: AgentState) -> dict:
        artefact = state["pending_artefact"]
        display = _format_artefact_display(artefact)

        # Pause graph — CLI receives display string in __interrupt__
        user_decision = interrupt(display)

        sources = list(state.get("tool_results") or [])

        if str(user_decision).lower().strip() in ("y", "yes"):
            approved_by = _get_username()
            artefact_id = save_artefact(
                artefact["type"],
                artefact["content"],
                artefact["video_ids"],
                approved_by,
                qdrant_client=qdrant_client,
            )
            answer = (
                f"Saved {artefact['type']} to the knowledge base.\n"
                f"  ID       : {artefact_id}\n"
                f"  Approved : {approved_by}\n"
                f"  Videos   : {', '.join(artefact['video_ids'])}"
            )
        else:
            answer = "Artefact discarded."

        return {
            "pending_artefact": None,
            "answer": answer,
            "sources": sources,
        }

    return ask_approval


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def route_after_run_tool(state: AgentState) -> Literal["ask_approval", "think"]:
    if state.get("pending_artefact"):
        return "ask_approval"
    return "think"


def route_after_think(state: AgentState) -> Literal["run_tool", "respond"]:
    last = state["messages"][-1]
    if _get_tool_calls(last):
        return "run_tool"
    return "respond"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_graph(
    qdrant_client: QdrantClient,
    embed_model: SentenceTransformer,
    ollama_host: str,
    model: str,
    generate_model: str,
    checkpointer=None,
):
    think = make_think_node(ollama_host, model)
    run_tool = make_run_tool_node(qdrant_client, embed_model, ollama_host, generate_model)
    respond = make_respond_node()
    ask_approval = make_ask_approval_node(qdrant_client)

    builder = StateGraph(AgentState)
    builder.add_node("think", think)
    builder.add_node("run_tool", run_tool)
    builder.add_node("respond", respond)
    builder.add_node("ask_approval", ask_approval)

    builder.set_entry_point("think")
    builder.add_conditional_edges(
        "think",
        route_after_think,
        {"run_tool": "run_tool", "respond": "respond"},
    )
    builder.add_conditional_edges(
        "run_tool",
        route_after_run_tool,
        {"ask_approval": "ask_approval", "think": "think"},
    )
    builder.add_edge("ask_approval", END)
    builder.add_edge("respond", END)

    return builder.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Startup checks
# ---------------------------------------------------------------------------


def _check_qdrant(qdrant_host: str) -> QdrantClient:
    host, _, port_str = qdrant_host.partition(":")
    port = int(port_str) if port_str else 6333
    client = QdrantClient(host=host, port=port)
    try:
        client.get_collections()
    except Exception as exc:
        print(f"ERROR: Cannot reach Qdrant at {qdrant_host}: {exc}", file=sys.stderr)
        sys.exit(1)
    return client


def _check_ollama(ollama_host: str) -> None:
    url = f"http://{ollama_host}/api/tags"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
    except Exception as exc:
        print(f"ERROR: Cannot reach Ollama at {ollama_host}: {exc}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _print_answer(answer: str, sources: list) -> None:
    print()
    print(answer)
    if sources:
        print()
        print("Sources:")
        seen: set = set()
        n = 1
        for s in sources:
            vid = s["video_id"]
            ts = float(s["timestamp_start"])
            key = (vid, ts)
            if key in seen:
                continue
            seen.add(key)
            score = s.get("score", "")
            score_str = f"  [{score}]" if score else ""
            print(f"  {n}. {vid} @ {ts:.1f}s{score_str}")
            n += 1
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    qdrant_host = os.environ.get("QDRANT_HOST", "localhost:6333")
    ollama_host = os.environ.get("OLLAMA_HOST", "localhost:11434")
    model = os.environ.get("AGENT_MODEL", "qwen2.5:7b")
    generate_model = os.environ.get("GENERATE_MODEL", model)
    embed_model_name = os.environ.get("EMBED_MODEL", "intfloat/multilingual-e5-large")

    print("=== HPC Video Knowledge-Base Agent ===")
    print(f"  Qdrant   : {qdrant_host}")
    print(f"  Ollama   : {ollama_host}")
    print(f"  LLM      : {model}  (tool-calling)")
    print(f"  Generate : {generate_model}  (summarise / playlist)")
    print(f"  Embed    : {embed_model_name}")
    print()

    print("Checking services...", end=" ", flush=True)
    qdrant_client = _check_qdrant(qdrant_host)
    _check_ollama(ollama_host)
    print("OK")

    print("Loading embed model...", end=" ", flush=True)
    embed_model = SentenceTransformer(embed_model_name)
    print("OK")
    print()

    checkpointer = MemorySaver()
    graph = build_graph(qdrant_client, embed_model, ollama_host, model, generate_model, checkpointer)

    # One thread_id per CLI session — the checkpointer accumulates message
    # history so the agent remembers what it said in earlier turns.
    session_thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_thread_id}}
    first_turn = True

    print("Type your question or 'exit' to quit.")
    print()

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

        if not user_input:
            continue
        if user_input.lower() == "exit":
            sys.exit(0)

        # First turn seeds the system prompt; subsequent turns only add the new
        # user message — the checkpointer carries the full history forward.
        if first_turn:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ]
            first_turn = False
        else:
            messages = [{"role": "user", "content": user_input}]

        state: AgentState = {
            "messages": messages,
            "tool_results": [],
            "pending_artefact": None,
            "answer": "",
            "sources": [],
        }

        result = graph.invoke(state, config=config)

        # Handle approval gate — loop in case of nested interrupts
        while result.get("__interrupt__"):
            interrupts = result["__interrupt__"]
            print(interrupts[0].value)
            print()
            try:
                decision = input("Save this to the knowledge base? [y/n] ").strip()
            except (EOFError, KeyboardInterrupt):
                decision = "n"
            result = graph.invoke(Command(resume=decision), config=config)

        _print_answer(result["answer"], result["sources"])


if __name__ == "__main__":
    main()
