# 10-agent — Docker

How to build and run the agent in a container.

---

## Build the image

```bash
bash 10-agent/docker/build.sh
```

Or manually from the project root:

```bash
docker build -f 10-agent/docker/Dockerfile -t slickplus/agent:latest .
```

---

## Run with the full stack (recommended)

Start all background services (Qdrant, Ollama, embed-server, index-server):

```bash
./restart-services-docker.sh
```

Then start an interactive agent session:

```bash
docker compose run --rm agent
```

The agent connects to Qdrant and Ollama using the internal Docker service hostnames defined in `docker-compose.yml`. Type a question at the `>` prompt. Type `exit` to quit.

---

## Run standalone (without docker compose)

Requires Qdrant and Ollama already running locally.

```bash
docker run -it \
  --network host \
  -e QDRANT_HOST=localhost:6333 \
  -e OLLAMA_HOST=localhost:11434 \
  -e AGENT_MODEL=qwen2.5:3b \
  -e GENERATE_MODEL=llama3:latest \
  -e EMBED_MODEL=intfloat/multilingual-e5-large \
  -v "$(pwd)/.hf_cache:/root/.cache/huggingface" \
  slickplus/agent:latest
```

`--network host` lets the container reach Qdrant and Ollama on your machine's localhost ports.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `QDRANT_HOST` | `localhost:6333` | Qdrant host:port |
| `OLLAMA_HOST` | `localhost:11434` | Ollama host:port |
| `AGENT_MODEL` | `qwen2.5:3b` | Ollama model for tool-calling (think node) |
| `GENERATE_MODEL` | same as `AGENT_MODEL` | Ollama model for generation (summarise / playlist) |
| `EMBED_MODEL` | `intfloat/multilingual-e5-large` | HuggingFace embed model |
| `HF_HOME` | `/root/.cache/huggingface` | HuggingFace model cache — bind-mount `.hf_cache` here to avoid re-downloading |

---

## Notes

- Model weights are **not** baked into the image. The HuggingFace cache (`.hf_cache/`) is bind-mounted from the project root so `multilingual-e5-large` is only downloaded once.
- The Ollama model (`qwen2.5:3b`) must be pulled into the Ollama volume before the agent starts. `restart-services-docker.sh` does this automatically.
- The agent is interactive (`stdin_open: true`, `tty: true`) — always start it with `-it` or `docker compose run`.
- Conversation history is in-memory only and does not persist when the container exits.
