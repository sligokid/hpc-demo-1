# 004 — Test suite

## Parent PRD

`prd/4.metadata/prd.md`

## What to build

A pytest test suite for `analyze.py` that mocks at the HTTP boundary (`requests.post`) and tests all externally observable behaviour: prompt construction, happy path JSON output, stdin path, and all four error paths. No real Ollama process or network call is required to run the tests.

## Acceptance criteria

- [ ] Tests can be run with `pytest` from the project root with no Ollama process running
- [ ] Prompt construction: given a known transcript string, assert the prompt sent to Ollama contains the transcript text and describes all five required output fields
- [ ] Happy path: mock `requests.post` to return a valid five-field JSON string; assert `analyze.py` prints the correct parsed dict and exits 0
- [ ] Stdin path: monkeypatch `sys.stdin` with a known string, pass `--transcript -`; assert correct output
- [ ] Empty transcript: assert exit code 1 and an error message on stderr
- [ ] `ConnectionError`: mock `requests.post` to raise `ConnectionError`; assert exit code 1 and message mentioning `ollama serve`
- [ ] Non-2xx HTTP response: mock a 500 response; assert exit code 1 and status code in error output
- [ ] Invalid JSON response: mock a non-JSON string response; assert exit code 1 and raw response in error output
- [ ] `--model` flag: assert the model name in the request body matches the flag value

## Blocked by

- `issues/001-core-script-happy-path.md`
- `issues/002-stdin-support.md`
- `issues/003-error-handling.md`

## User stories addressed

All testing decisions described in `prd/4.metadata/prd.md` under "Testing Decisions".
