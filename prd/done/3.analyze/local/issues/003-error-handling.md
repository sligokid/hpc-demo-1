# 003 — Error handling

## Parent PRD

`prd/4.metadata/prd.md`

## What to build

Add all four error paths to `analyze.py` so that every failure mode produces a clear human-readable message on stderr and exits with a non-zero code. No failure should produce silent output or exit 0.

| Condition | Behaviour |
|---|---|
| Empty transcript | Print error, exit 1 |
| Ollama not running (`ConnectionError`) | Print message directing user to `ollama serve`, exit 1 |
| Ollama HTTP error (non-2xx) | Print status code and response body, exit 1 |
| Model returns invalid JSON | Print raw model response for debugging, exit 1 |

## Acceptance criteria

- [ ] Passing an empty transcript (empty file or empty stdin) prints an error message and exits 1
- [ ] When Ollama is not running, the error message tells the user to run `ollama serve` and exits 1
- [ ] A non-2xx HTTP response from Ollama prints the status code and body, then exits 1
- [ ] A model response that is not valid JSON prints the raw response and exits 1
- [ ] All error messages go to stderr, not stdout
- [ ] Script never exits 0 when any of the above conditions occur
- [ ] A shell pipeline (`infer.py | analyze.py`) propagates the non-zero exit code correctly

## Blocked by

- `issues/001-core-script-happy-path.md`

## User stories addressed

- User story 12: clear error message if Ollama is not running
- User story 13: clear error message if model returns malformed JSON
- User story 14: exit with non-zero code on any failure
- User story 19: empty transcript produces an error rather than nonsense metadata
