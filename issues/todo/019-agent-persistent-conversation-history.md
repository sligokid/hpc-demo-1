## Agent: persistent conversation history and multi-user sessions

Currently `agent.py` creates a fresh `AgentState` for every question at the `>` prompt. Conversation history (`messages`) lives only inside the `graph.invoke()` call and is discarded when it returns. There is no memory between turns and no concept of concurrent users or sessions.

### What this means

- Follow-up questions ("tell me more about that video") will not work — the agent has no context from the previous turn.
- The CLI is single-process, single-user, serial — no multi-user isolation exists.

### What is needed

1. **LangGraph checkpointer** — add a `SqliteSaver` (local) or `PostgresSaver` (production) checkpointer to the compiled graph, keyed on a `thread_id` per session. LangGraph replays and appends to the stored message list on each `graph.invoke()`.
2. **Session ID** — assign a `thread_id` per user session (UUID on CLI startup; derived from auth token in a server context). Pass it as `{"configurable": {"thread_id": session_id}}` to `graph.invoke()`.
3. **Server layer** (for multi-user) — wrap the graph in a FastAPI or WebSocket server that routes each connection to its own `thread_id`. Without this, concurrent users share state.

### Suggested approach for local CLI (quick win)

```python
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string("agent_history.db")
graph = builder.compile(checkpointer=checkpointer)

# per session
config = {"configurable": {"thread_id": str(uuid.uuid4())}}
graph.invoke(initial_state, config=config)
```

This gives persistent multi-turn memory within a session and isolates concurrent sessions by `thread_id`, with no server required.

### Blocked by

Nothing — can be added on top of the current `agent.py` independently.
