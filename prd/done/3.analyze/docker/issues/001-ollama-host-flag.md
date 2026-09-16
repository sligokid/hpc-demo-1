## Parent PRD

`prd/4.extract/docker/prd.md`

## What to build

Add an `--ollama-host` flag to `analyze.py` so the caller can specify where Ollama is running. Currently the URL is hardcoded as `http://localhost:11434/api/generate`. Replace it with a URL constructed from the flag value. Update the connection error message to include the host that was used. Add tests covering URL construction, the error message, and the default.

See PRD §Implementation Decisions > `analyze.py` and §Testing Decisions.

## Acceptance criteria

- [ ] `analyze.py` accepts `--ollama-host` with default `localhost:11434`
- [ ] The URL used for `requests.post` is `http://<ollama_host>/api/generate`
- [ ] Passing `--ollama-host ollama:11434` causes the call to go to `http://ollama:11434/api/generate`
- [ ] The connection error message includes the value of `--ollama-host`
- [ ] Omitting `--ollama-host` still works (default `localhost:11434`) — existing usage not broken
- [ ] Test: mock `requests.post`; assert URL is `http://ollama:11434/api/generate` when `--ollama-host ollama:11434` is passed
- [ ] Test: mock `requests.post` raising `ConnectionError`; assert exit code 1 and error output contains the host value
- [ ] Test: assert default URL is `http://localhost:11434/api/generate` when flag is omitted

## Blocked by

None - can start immediately.

## User stories addressed

- User story 5
- User story 6
- User story 14
- User story 15
- User story 16
