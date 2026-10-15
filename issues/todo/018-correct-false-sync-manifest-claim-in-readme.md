## Parent PRD

`prd/task-2-company-brain/prd.md`

## Problem

PR #9 (`75f26b0`, "task-2-part-9-readmes") added a detailed "How it Works" section to `4-file-sync/README.md` that contains a **factually wrong claim about the control flow**:

> The pipeline (`Z-poll`) reads `logs/sync-manifest.txt` on each cycle and submits a new array job for any file not yet marked `.done`.

Nothing reads that file. It is write-only:

```
$ grep -rn "sync-manifest" --include=*.sh --include=*.py . | grep -v "^./logs"
./4-file-sync/sync.sh:7:      # comment
./4-file-sync/sync.sh:26:MANIFEST="${LOG_DIR}/sync-manifest.txt"
./4-file-sync/test-sync.sh:72,85,99,101      # test assertions
./4-file-sync/docker/test-local.sh:89,102,116,118
```

`4-file-sync/sync.sh` *writes* it. The only readers are test scripts asserting on it. `Z-poll` → `pipeline-hpc-submit.sh` never touches it — instead it globs the inbox directly and builds a **separate, per-cycle** manifest:

```bash
# pipeline-hpc-submit.sh:33
MANIFEST="$PWD/logs/pipeline-manifest-$(date +%Y%m%d-%H%M%S).txt"

# pipeline-hpc-submit.sh:43-48
for f in "$dir"/*.{mp3,mp4,wav,flac,m4a,ogg}; do
    [ -f "$f" ] || continue
    [ -f "$f.done" ] && continue
    echo "$f"
done > "$MANIFEST"
```

There are two distinct manifests with confusingly similar names:

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `logs/sync-manifest.txt` | `4-file-sync/sync.sh` | tests only | audit log of what arrived from Drive |
| `logs/pipeline-manifest-<ts>.txt` | `pipeline-hpc-submit.sh` | `pipeline-hpc-sbatch.sh` | per-cycle work list for the SLURM array |

This matters practically, not just pedantically. The documented model — "poller reads the sync manifest" — implies a clean handoff between stages. The real model is that the poller **re-globs the filesystem**, which is precisely why the poison-pill retry loop in `issues/013-bound-retry-loop-for-permanently-failing-files.md` is possible: a file is rediscovered on every cycle because nothing records "already attempted and failed" anywhere the poller consults. The documented architecture would not have that bug.

## What to build

Correct the description of the control flow, and make the two manifests distinguishable.

- Fix the false claim in `4-file-sync/README.md`. State that `Z-poll` scans `sync/input/` directly via `pipeline-hpc-submit.sh`, and that `logs/sync-manifest.txt` is an audit log written by the sync stage, not an input to the pipeline.
- Document both manifest files and their distinct roles in the root `README.md` Monitoring section, which currently mentions only `sync-manifest.txt` and `pipeline-manifest-*.txt` without explaining the difference.
- Consider whether `sync-manifest.txt` earns its place at all. If it is only for auditing, say so. If the intent was for it to drive the pipeline, that intent was never implemented and the docs should not imply it.
- Note the re-glob behaviour explicitly, since it is the mechanism behind the unbounded retry issue. Cross-reference `issues/013-bound-retry-loop-for-permanently-failing-files.md`.

PR #9 otherwise improved this file substantially — the "How it Works" and "Sample Output" sections are accurate apart from this one claim. Fix that claim rather than reverting the section.

## Acceptance criteria

- [ ] `4-file-sync/README.md` no longer claims `Z-poll` reads `logs/sync-manifest.txt`
- [ ] The corrected text states that the poller globs `sync/input/` directly
- [ ] The root `README.md` Monitoring section explains the difference between `sync-manifest.txt` and `pipeline-manifest-<ts>.txt`
- [ ] `sync-manifest.txt` is documented as an audit log (or removed if it has no consumer)
- [ ] The re-glob behaviour is documented, with a cross-reference to `issues/013-bound-retry-loop-for-permanently-failing-files.md`
- [ ] No other README claims a script reads a file it does not — spot-check the per-stage READMEs added in PR #9 for the same class of error
- [ ] Existing tests still pass

## Blocked by

- None - can start immediately

## User stories addressed

- An engineer debugging why a file is reprocessed reads an accurate account of the control flow rather than an incorrect one.
- The retry-loop defect in `issues/013` is traceable to a documented mechanism, so the fix and its rationale are discoverable from the docs.
