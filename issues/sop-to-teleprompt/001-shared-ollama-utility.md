## Parent PRD

`issues/prd-sop-to-teleprompter.md`

## What to build

Extract the `_call_ollama` function from `11-sop/sop.py` into a new shared module `11-sop/ollama_utils.py`. Update `sop.py` to import from it. This unblocks `teleprompter.py` from duplicating the same code.

No behaviour changes — purely a refactor. All existing tests must still pass.

## Acceptance criteria

- [ ] `11-sop/ollama_utils.py` exists and contains `_call_ollama`
- [ ] `11-sop/sop.py` imports `_call_ollama` from `ollama_utils` instead of defining it inline
- [ ] `python -m pytest 11-sop/test_sop.py` passes without modification

## Blocked by

None — can start immediately.

## User stories addressed

- Enables the shared LLM caller required by the SOP to Teleprompter workflow (Technical Design section of PRD)
