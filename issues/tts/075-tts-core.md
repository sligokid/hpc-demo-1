## Parent PRD

`issues/prd.md`

## What to build

The core `12-tts/tts.py` Python module and its unit tests. This is the complete standalone TTS engine: it reads a `{stem}.teleprompter.md` file, extracts only the Audio field content from the two-column table structure, strips `[PAUSE]` markers and residual markdown, splits the plain text into sentence-boundary chunks of at most 4096 characters, calls `POST /v1/audio/speech` on Ollama phonon for each chunk, and concatenates all WAV responses into a single `{stem}.teleprompter.wav` output file using the stdlib `wave` module. The module is idempotent (skips if output already exists) and exposes a clean CLI (`--input`, `--output`, `--ollama-host`, `--voice`).

Also delivers `12-tts/requirements.txt` (`requests` only) and `12-tts/test_tts.py` with mocked HTTP calls.

See the Implementation Decisions and Testing Decisions sections of the PRD for full API contract, extraction regex, chunking strategy, and test scope.

## Acceptance criteria

- [ ] `12-tts/tts.py` exists with a `generate(input_path, output_stem, ollama_host, voice)` function and a `main()` CLI entry point
- [ ] Audio fields are correctly extracted from teleprompter markdown; visual cues and headings are excluded
- [ ] `[PAUSE]` markers and residual markdown symbols are stripped before chunking
- [ ] Text is split at sentence boundaries; no chunk exceeds 4096 characters
- [ ] All chunk WAV responses are concatenated into a single valid WAV file (16-bit, mono, 24kHz)
- [ ] Module returns early without any API call if `{stem}.teleprompter.wav` already exists
- [ ] CLI accepts `--input`, `--output`, `--ollama-host`, `--voice` flags
- [ ] `12-tts/requirements.txt` contains only `requests`
- [ ] `12-tts/test_tts.py` passes: extraction, stripping, chunking, WAV concat, and idempotency are each covered with mocked `requests.post`

## Blocked by

None — can start immediately.

## User stories addressed

- User story 1
- User story 2
- User story 4
- User story 5
- User story 6
- User story 7
- User story 15
- User story 16
- User story 18
- User story 19
- User story 20
