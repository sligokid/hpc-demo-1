## Parent PRD

`prd/task-2-company-brain/prd.md`

## What to build

Deploy Qdrant and the embedding worker as persistent SLURM service jobs on LUMI, alongside the existing Ollama service. Follows the established Singularity SIF + sbatch service job pattern used in earlier stages.

Deliverables:
- **`5-embed/hpc/qdrant-serve-sbatch.sh`** — SLURM service job that pulls/runs the Qdrant SIF, exposes port 6333 on the allocated node
- **`5-embed/hpc/embeddings-serve-sbatch.sh`** — SLURM service job that runs `embed-server.py` inside the qdrant-embeddings-api SIF, connects to Qdrant

Also requires building and pushing the amd64 embed-server Docker image and pulling SIFs on LUMI:
```bash
docker buildx build --platform linux/amd64 -t sligokid/embeddings-api:latest --push 5-embed/
singularity pull /scratch/project_465003209/mcgowank/embeddings-api.sif docker://sligokid/embeddings-api:latest
singularity pull /scratch/project_465003209/mcgowank/qdrant.sif docker://qdrant/qdrant:latest
```

Follow existing HPC script conventions from `CLAUDE.md`: use `SLURM_SUBMIT_DIR` for project root in sbatch scripts, bind project root as `/workspace`, use `bash -c "..."` wrapper for Singularity calls.

See PRD: Phase 3 — HPC section and Deliverables #20–21.

## Acceptance criteria

- [ ] `sbatch 5-embed/hpc/qdrant-serve-sbatch.sh` starts Qdrant on a SLURM node; dashboard accessible at `:6333`
- [ ] `sbatch 5-embed/hpc/embeddings-serve-sbatch.sh` starts embed-server and connects to Qdrant (visible in logs)
- [ ] Full pipeline processes a real audio file through all 5 stages on GPU nodes
- [ ] `python search.py` returns results from the HPC-indexed Qdrant collection
- [ ] `python graph.py` exports `graph.json`; `graph.html` renders correctly when opened from Google Drive
- [ ] `python playlist.py --user user@org.com` returns a playlist from the HPC index
- [ ] All outputs rclone correctly to Google Drive alongside transcripts

## Blocked by

- Blocked by `issues/005-docker-packaging.md` (amd64 Docker image must exist before SIF can be built)

## User stories addressed

- The end-to-end pipeline runs at production scale on GPU hardware, meeting the latency target of results searchable within 15 minutes of upload for a 10-minute audio file (PRD Goal 8, Success Criteria).
