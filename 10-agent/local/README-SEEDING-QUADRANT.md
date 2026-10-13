# 10-agent/local

Local development helpers for the agent layer. These scripts let you seed a
local Qdrant instance with HPC pipeline output files so the agent tools have
real data to query during development.

## Pre-requisites

Three services must be running before seeding. Start them in separate
terminals from the **project root** with the venv active:

```bash
# 1 — Qdrant (Docker) on :6333
7-index/local/1-start-qdrant.sh

# 2 — Embed server (multilingual-e5-large) on :8765
6-embed/local/1-start-embed-server.sh

# 3 — Index server (writes to Qdrant) on :8766
7-index/local/2-start-index-server.sh
```

## Seeding Qdrant

Place HPC output files under `sync/output/{lang}/`:

```
sync/output/
  en/
    video1.segments.json    # required
    video1.analysis.json    # optional
    video1.sentiment.json   # optional
  es/
    ...
```

Then run:

```bash
# All languages
./10-agent/local/seed-qdrant.sh

# Single language
./10-agent/local/seed-qdrant.sh --lang en

# Re-index files that were already processed
./10-agent/local/seed-qdrant.sh --force

# Custom output directory
./10-agent/local/seed-qdrant.sh --out-dir /path/to/outputs
```

The script activates the project venv automatically and delegates to
`seed_qdrant.py` at the project root.

A `.indexed` sidecar file is written next to each processed
`.segments.json`. Subsequent runs skip those files unless `--force` is
passed.

## Verifying indexed data

```bash
# Scroll the video_metadata collection
7-index/local/4-scroll-collection.sh
```

## Files

| File | Purpose |
|---|---|
| `seed-qdrant.sh` | Convenience wrapper around `seed_qdrant.py` |
| `.env.example` | Environment variable template for agent configuration |
