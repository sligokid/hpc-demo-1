## Parent PRD

`issues/prd-v1.md`

## What to build

Extend `tools.py` with three write-side functions and add the approval gate (interrupt node) to the LangGraph graph in `agent.py`. This delivers the governance workflow: the agent generates a draft artefact, pauses for human `y/n` approval, and only persists to Qdrant if approved.

**New tool functions in `tools.py`:**
- `generate_summary(video_id)` — retrieves the full transcript via `get_full_transcript`, sends it to Qwen via Ollama with a summarisation prompt, returns a draft summary string. Does not persist anything.
- `generate_playlist(goal)` — calls `search_knowledge_base` multiple times with varied sub-queries derived from the goal, reasons over results via Qwen, returns an ordered list of `{video_id, title, timestamp_start, timestamp_end, reason}`. Does not persist anything.
- `save_artefact(type, content, video_ids, approved_by)` — creates the `video_artefacts` Qdrant collection if it does not exist (1-dim placeholder vector, schema-free payload), then upserts the artefact with `type`, `content`, `source_video_ids`, `approved_by`, `approved_at`. Uses a deterministic UUID keyed on `type + video_ids` so reruns overwrite rather than duplicate.

**Approval gate in `agent.py`:**
- A new `ask_approval` node is added to the LangGraph graph
- When `think` determines a write operation is needed, it routes to `ask_approval` instead of `respond`
- `ask_approval` uses LangGraph `interrupt()` to pause execution, display the draft artefact in the terminal, and prompt `Save this <type> to the knowledge base? [y/n]`
- On `y`: resumes, calls `save_artefact`, prints confirmation (artefact ID, approver via `os.getlogin()`, timestamp)
- On `n`: resumes, discards silently, returns to `>` prompt
- `save_artefact` is NOT exposed as a tool the LLM can call directly — it is only reachable via the `ask_approval` node. This is enforced at the graph level.

**Tests:**
- `generate_summary` returns a non-empty string given a mock transcript
- `generate_playlist` returns an ordered list with required fields given mock search results
- `save_artefact` writes to `video_artefacts` with all required fields including `approved_by` and `approved_at`
- Graph test: a write-triggering input routes to `ask_approval` and the graph halts awaiting interrupt input
- Graph test: approving (`y`) calls `save_artefact` and returns to the prompt
- Graph test: rejecting (`n`) does not call `save_artefact`

## Acceptance criteria

- [ ] `generate_summary` produces a draft summary for a given video without writing anything
- [ ] `generate_playlist` produces an ordered list of `{video_id, title, timestamp_start, timestamp_end, reason}` for a given goal
- [ ] Asking the agent to summarise a video displays the draft and prompts `[y/n]` before saving
- [ ] Asking the agent to build a playlist displays the draft and prompts `[y/n]` before saving
- [ ] Approving saves the artefact to Qdrant `video_artefacts` with `approved_by` (OS username) and `approved_at` (ISO timestamp)
- [ ] Rejecting discards silently — no write to Qdrant, no error message
- [ ] `save_artefact` cannot be triggered by the LLM directly — only via the approval node
- [ ] The `video_artefacts` collection is created automatically on first write if it does not exist
- [ ] `pytest 10-agent/tests/` passes including all new write-path and graph tests

## Blocked by

- Blocked by `issues/002-basic-rag-chat-local.md`

## User stories addressed

- User story 9 (onboarding playlist generation)
- User story 10 (video summary generation)
- User story 11 (y/n approval prompt)
- User story 12 (rejected artefacts discarded silently)
- User story 13 (approved artefacts saved with identity and timestamp)
- User story 17 (tools.py remains pure and testable)
