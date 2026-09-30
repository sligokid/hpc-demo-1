## Parent PRD

`prd/task-2-company-brain/prd.md`

## Problem

`pipeline.py` catches bare `Exception` in all four stage handlers and prints only `str(exc)`. There is no `import traceback` anywhere in the file.

```python
# pipeline.py:217-218
except Exception as exc:
    print(f"  INFER ERROR — {exc}")
```

The consequence is severe: **226 consecutive identical failures produced zero diagnostic signal.**

```
$ grep -rh "INFER ERROR" logs/ | sort | uniq -c | sort -rn
    226   INFER ERROR — float division by zero
    226   INFER ERROR —
```

Two things are lost. First, the stack trace — we cannot tell whether the division by zero comes from `transformers` chunking, `librosa`, or our own code. Second, the exception *type* — the empty-message variant is an exception whose `str()` is blank, which is a completely different failure from `ZeroDivisionError` and is currently indistinguishable from a crash in the log.

Every future inference bug inherits this blindness. This issue is the prerequisite for diagnosing `issues/012-float-division-by-zero-in-inference.md`.

## What to build

Log the full traceback for every stage failure in `pipeline.py`, so a failed array task leaves enough evidence in `logs/<jobid>_<taskid>.out` to diagnose the failure without reproducing it interactively.

Concretely:

- `import traceback` at module top.
- In each of the four `except` blocks (infer `pipeline.py:217`, analyze `pipeline.py:238`, sentiment `pipeline.py:255`, embed/index `pipeline.py:268`), emit `traceback.format_exc()` in addition to the existing one-line message.
- Include the exception type in the one-liner, so blank-`str()` exceptions are identifiable: `INFER ERROR — ZeroDivisionError: float division by zero` rather than `INFER ERROR — `.
- Identify the file being processed in the traceback output. The handler already has `audio_path` in scope, so a failure line should name the file even when the exception message is empty.

Do not change control flow — the `errors += 1; continue` behaviour stays as is. This is purely about making failures legible.

## Acceptance criteria

- [ ] `traceback` is imported in `pipeline.py`
- [ ] All four `except` blocks print `traceback.format_exc()`
- [ ] Each one-line error message includes the exception type name
- [ ] A deliberately-failing file produces a log containing the originating file path, the exception type, and a stack trace
- [ ] An exception with an empty `str()` is still identifiable by type in the log
- [ ] `errors` counting and the `sys.exit(1)` on failure are unchanged
- [ ] No traceback text is written to the synced output files in `sync/output/` — logs only

## Blocked by

- None - can start immediately

## User stories addressed

- An engineer can diagnose a failing pipeline job from its log file alone, without an interactive reproduction on a GPU node.
- Failures that have occurred hundreds of times are distinguishable from each other rather than all reading `INFER ERROR — `.
