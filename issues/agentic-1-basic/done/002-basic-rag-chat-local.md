## Parent PRD

`issues/prd-v1.md`

## What to build

Implement the LangGraph agent graph and CLI loop in `agent.py`, and a `local/run.sh` launch script. This delivers the first end-to-end demoable experience: a user types a question at a `>` prompt and receives a cited answer drawn from the Qdrant knowledge base.

The LangGraph graph has three nodes for the read-only path:
- `think` — Qwen (via Ollama) receives the conversation history and system prompt, decides which tool to call next or whether to respond
- `run_tool` — executes the tool function chosen by `think`, writes the result back to state
- `respond` — formats and prints the final answer with the sources block to the terminal

The graph cycles between `think` and `run_tool` until Qwen decides it has enough information to answer, then routes to `respond`. The interrupt/approval node is NOT part of this issue — that is `issues/003`.

The CLI loop in `agent.py`:
- Prints a startup banner and confirms Qdrant and Ollama are reachable
- Exits with a non-zero code and a clear error message if either service is unreachable
- Accepts user input at a `>` prompt
- Runs the graph for each input
- Prints the answer and sources block
- Loops until the user types `exit`

`local/run.sh` sets `QDRANT_HOST`, `OLLAMA_HOST`, `HF_HOME`, and any other required env vars, then calls `python agent.py`. It reads from `local/.env.example` as a reference.

Graph tests (headless, no terminal) verify:
- A question input routes through `think` → `run_tool` → `respond` without hitting the interrupt node
- The final state contains a non-empty `answer` and a non-empty `sources` list

## Acceptance criteria

- [ ] `bash 10-agent/local/run.sh` starts the agent and presents a `>` prompt
- [ ] Typing a question returns an answer with a numbered `Sources:` block (video title, timestamp, creator, score)
- [ ] The agent calls multiple tools autonomously if needed before responding (multi-hop)
- [ ] Questions in any of the five supported languages (en, es, fr, zh, ar) return results filtered to that language
- [ ] Startup fails fast with a clear error message if Qdrant is unreachable
- [ ] Startup fails fast with a clear error message if Ollama is unreachable
- [ ] Typing `exit` terminates the process cleanly with exit code 0
- [ ] LangGraph graph definition is importable and testable without a running terminal
- [ ] `pytest 10-agent/tests/` passes including graph path tests (mocked Qdrant + Ollama)

## Blocked by

- Blocked by `issues/001-scaffold-read-tools.md`

## User stories addressed

- User story 5 (natural-language question at `>` prompt)
- User story 6 (numbered sources block)
- User story 7 (multilingual filtering)
- User story 8 (creator-based search)
- User story 14 (agent works autonomously across multiple tool calls)
- User story 15 (full transcript retrieval)
- User story 16 (reasoning visible — which videos searched)
- User story 18 (graph separate from CLI entry point)
- User story 22 (clean exit on unreachable services)
