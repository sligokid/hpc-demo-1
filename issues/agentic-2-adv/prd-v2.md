# PRD: SLICK+ Knowledge Agent v2 — Desktop UI & Extended Capabilities

## Problem Statement

The v1 terminal agent is powerful but accessible only to developers comfortable with a CLI. Broader teams — operations managers, HR, compliance officers, frontline trainers — need to query the video knowledge base without opening a terminal. Additionally, v1 deferred several capabilities that are needed for production use: a visual chat interface with clickable citations, physical video delivery at specific timestamps, streaming responses, MCP tool access for AI-native workflows, and governance metadata on indexed content.

## Solution

A thin HTTP layer (`chat_server.py`) wraps the existing LangGraph agent and exposes a `/chat` endpoint. A Gradio chat UI runs locally on the developer's PC, opening in a browser tab as a popup-style interface. The same `tools.py` and LangGraph graph from v1 power the backend — no agent logic changes. Additional v2 capabilities (MCP server, video deep-links, streaming, metadata governance fields) are layered on top of the same foundation.

## User Stories

1. As a non-technical user, I want to open a browser tab on my PC and type questions to the knowledge base, so that I do not need to use a terminal.
2. As a user, I want the chat interface to display source citations as clickable cards showing video title, creator, and timestamp, so that I can navigate directly to the relevant moment in a video.
3. As a user, I want the agent's response to stream word-by-word into the chat window, so that I do not wait for the full answer before reading begins.
4. As a user, I want to click a timestamp link and have it open the video at that exact moment, so that I can verify the source without scrubbing manually.
5. As a user, I want draft artefacts (summaries, playlists, checklists) to appear in the chat UI with an approve/reject button, so that the governance workflow is visual rather than terminal-based.
6. As a user, I want approved artefacts to be saved and confirmed in the chat UI with an artefact ID and timestamp, so that I have a visual record of what I approved.
7. As a developer, I want a `chat_server.py` FastAPI service that wraps the LangGraph agent and exposes a `/chat` endpoint, so that any UI can consume the agent without re-implementing agent logic.
8. As a developer, I want the `chat_server.py` added as a service in the existing `docker-compose.yml`, so that `docker compose up` starts the full stack including the UI.
9. As a developer, I want to run the UI locally with `docker run -p 7860:7860 slickplus/chat:latest` and open `localhost:7860` in a browser, so that the desktop popup experience requires no installation.
10. As a developer, I want an MCP server (`mcp_server.py`) that exposes the tools from `tools.py` as MCP-compatible tool definitions, so that Claude Code and other MCP clients can query the knowledge base directly.
11. As a developer, I want the MCP server to run as a stdio process that Claude Code can spawn, so that no additional port or service is required for MCP usage.
12. As a developer, I want `mcp_server.py` to share `tools.py` with the agent and chat server without any code duplication, so that tool logic is maintained in one place.
13. As a developer, I want video deep-link URLs included in every source citation, so that the UI and MCP clients can construct `mpv video.mp4 --start=HH:MM:SS` commands or equivalent browser links.
14. As a developer, I want the agent to support physical video stitching via ffmpeg as an optional tool, so that users can request a compiled highlight reel from multiple videos.
15. As a developer, I want `review_status`, `reviewed_by`, `reviewed_at`, and `permissions` fields added to the `video_metadata` Qdrant collection, so that the governance layer can filter content by approval state and access level.
16. As a developer, I want the agent to filter search results by `review_status` and `permissions` when these fields are present, so that unapproved or restricted content is not surfaced to unauthorised users.
17. As a user, I want the chat UI to support multiple conversation sessions, so that I can switch between different lines of inquiry without losing context.

## Implementation Decisions

### Modules

**`10-agent/chat_server.py` — FastAPI HTTP wrapper**
Thin layer over the existing LangGraph agent. Exposes:
- `POST /chat` — accepts `{message, session_id}`, runs the agent graph, returns `{answer, sources, artefact?}` as JSON
- `GET /health` — liveness check

Streams responses using Server-Sent Events (SSE) so the Gradio UI can display tokens as they arrive. Does not duplicate any tool or agent logic — imports directly from `tools.py` and `agent.py`.

**`10-agent/ui.py` — Gradio chat interface**
Connects to `chat_server.py` via HTTP. Renders:
- Chat message bubbles for user and agent turns
- Source citation cards with video title, creator, timestamp, and score
- Approve/reject buttons when a draft artefact is present in the response
- Confirmation card on approval with artefact ID and timestamp

Runs on port 7860. Can be opened in any browser on the local machine.

**`10-agent/mcp_server.py` — MCP tool server**
Wraps the six tool functions from `tools.py` as MCP tool definitions using the MCP Python SDK. Runs as a stdio process. No new tool logic — pure transport layer. Registered in Claude Code's MCP config to enable direct knowledge base access from the terminal.

**`10-agent/Dockerfile.chat`**
Separate Dockerfile for the chat server + UI. Installs `fastapi`, `uvicorn`, `gradio` in addition to the base agent dependencies. Entrypoint starts both `chat_server.py` and `ui.py` via a process supervisor or a simple shell script.

### Interfaces

**`POST /chat` request/response**
```
Request:  { "message": "...", "session_id": "abc123" }
Response: { "answer": "...", "sources": [...], "artefact": null | { "type", "content", "draft_id" } }
```

**Approval endpoint**
```
POST /approve  { "draft_id": "...", "approved": true|false }
Response: { "artefact_id": "...", "approved_by": "...", "approved_at": "..." }
```

**MCP tool definitions (from `mcp_server.py`)**
- `search_knowledge_base` — same signature as `tools.py`
- `get_video_metadata` — same signature
- `get_full_transcript` — same signature
- `generate_summary` — same signature
- `generate_playlist` — same signature

`save_artefact` is not exposed via MCP — write operations require the approval gate which is only available in the agent and chat UI flows.

### Architecture decisions

- `chat_server.py` is a wrapper, not a rewrite. The LangGraph graph from v1 runs unchanged inside it.
- The Gradio UI communicates with `chat_server.py` over localhost HTTP — it does not import agent code directly. This keeps the UI decoupled from agent internals.
- The approval flow in the UI uses a `draft_id` returned in the `/chat` response. The server holds draft artefacts in memory (keyed by `draft_id`) until approved or rejected. Persistence of drafts across server restarts is out of scope.
- Physical video stitching uses `ffmpeg` as a subprocess called from a new `stitch_video(segments)` tool function in `tools.py`. It is only available if `ffmpeg` is present in the container.
- Metadata governance fields (`review_status` etc.) are added to `video_metadata` payloads via the existing `/metadata` endpoint in `7-index/index_server.py` — no schema migration is required since Qdrant payloads are schema-free.
- Streaming uses SSE from `chat_server.py`. Gradio's `gr.ChatInterface` supports SSE natively via its generator-based message handler.

## Testing Decisions

**`chat_server.py`** — test the `/chat` and `/approve` endpoints with `pytest` + `httpx` async client. Mock the LangGraph agent. Verify that a read-only response contains no `artefact` field. Verify that a write response contains a `draft_id`. Verify that `/approve` with `approved: true` calls `save_artefact` and returns an artefact ID.

**`mcp_server.py`** — test that each MCP tool definition matches the signature of its corresponding function in `tools.py`. Use the MCP Python SDK test utilities to drive tool calls headlessly.

**`ui.py`** — not unit tested. Gradio UIs are best validated via manual smoke testing.

## Out of Scope

- Public hosting of the UI — v2 UI runs on localhost only. Public deployment (reverse proxy, auth, HTTPS) is v3.
- Multi-user auth — session IDs are client-generated and unverified in v2.
- Mobile app — browser on PC only.
- Real-time collaboration — single user per session.

## Further Notes

- The Gradio UI port (7860) does not conflict with any existing service in `docker-compose.yml` (Qdrant: 6333/6334, Ollama: 11434, embed-server: 8765, index-server: 8766).
- The `mcp_server.py` stdio process can be registered in `.claude/mcp.json` at the project root so that Claude Code users on the project automatically have access to the knowledge base tools.
- Physical video stitching via ffmpeg requires video files to be accessible on the filesystem at the paths stored in Qdrant `file` payloads. On HPC this means the bind-mounted `/workspace` must include the original video files, not just audio.
- The `chat_server.py` service in `docker-compose.yml` uses internal Docker hostnames (`qdrant:6333`, `ollama:11434`) consistent with the v1 agent service.
