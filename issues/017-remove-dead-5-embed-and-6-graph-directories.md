## Parent PRD

`prd/task-2-company-brain/prd.md`

## Problem

Commit `ef97090` ("split 5-embed into 5-sentiment / 6-embed / 7-index / 8-search / 9-graph") reorganised the pipeline stages, but the two superseded directories were left behind on disk. They now contain no code at all — only stale job logs from before the split:

```
$ find 5-embed 6-graph -type f
5-embed/__pycache__/sentiment.cpython-310.pyc
5-embed/hpc/logs/qdrant-slurm-22320019.out
5-embed/hpc/logs/qdrant-slurm-22320019.err
5-embed/hpc/logs/embed-slurm-22320028.err
5-embed/hpc/logs/embed-slurm-22320028.out
5-embed/hpc/logs/embed-slurm-22320127.out
5-embed/hpc/logs/embed-slurm-22320127.err
6-graph/hpc/logs/graph-slurm-22320140.err
6-graph/hpc/logs/graph-slurm-22320140.out
6-graph/hpc/logs/graph-slurm-22323773.err
6-graph/hpc/logs/graph-slurm-22323773.out
```

Both are untracked (`git status` shows `?? 5-embed/` and `?? 6-graph/`), so they are not in version control and never were — they are pure local detritus. Nothing imports them: `pipeline.py:95-97` loads sentiment from `5-sentiment/sentiment.py`, the embed service is `6-embed/embed_server.py`, and the graph builder is `9-graph/graph.py`.

They are actively harmful, not merely untidy:

- The stale `hpc/logs/*.out` files contain job output from superseded service scripts with the old job names, which is confusing when diagnosing current service behaviour.
- A `.pyc` for a `sentiment.py` that no longer exists in that directory suggests code is still there.
- Anyone auditing the pipeline sees two stage directories that do nothing, and has to work out that `6-graph/` is not the graph stage (`9-graph/` is).
- The numbering collision (`5-embed` vs `5-sentiment`, `6-graph` vs `6-embed`) is precisely the kind of ambiguity that causes the wrong directory to be edited.

## What to build

Delete the two dead directories. No code changes — they are untracked leftovers with no references.

- Remove `5-embed/` and `6-graph/` entirely, including `__pycache__` and the stale `hpc/logs/`.
- Verify no script, config, or doc references either path before deleting. Check in particular that no `sbatch` invocation or `--output=` path still points into them.
- Confirm the live stage directories are the surviving ones: `5-sentiment/`, `6-embed/`, `7-index/`, `8-search/`, `9-graph/`.
- Add a guard so this does not recur: the `hpc/logs/` directories inside stage subdirectories are a recurring source of untracked noise. Consider adding `*/hpc/logs/` to `.gitignore` so per-stage log output is never committed, and confirm `logs/` at the root is handled consistently (it is currently untracked and listed in `.gitignore` only implicitly).
- Note: `.gitignore` currently has `checkpoints*`, `venv*`, `.hf_cache*`, `*__pycache__`, `*.DS_Store` — it does not cover `logs/`, which is why `logs/` shows up as untracked with 700+ files in `git status`.

## Acceptance criteria

- [ ] `5-embed/` and `6-graph/` are removed from disk
- [ ] No script, sbatch script, config, or README references either path
- [ ] The live stage directories (`5-sentiment/`, `6-embed/`, `7-index/`, `8-search/`, `9-graph/`) are confirmed as the surviving set
- [ ] `.gitignore` covers `logs/` and `*/hpc/logs/` so per-stage log output is never staged
- [ ] `git status` no longer shows untracked stage-log directories
- [ ] `pipeline.py` and all service scripts still run — no import or path breakage from the deletion
- [ ] Existing tests still pass

## Blocked by

- None - can start immediately

## User stories addressed

- A developer exploring the repository sees only the stage directories that are live, with no ambiguity about which is which.
- Stale logs from superseded service scripts no longer mislead debugging of current services.
