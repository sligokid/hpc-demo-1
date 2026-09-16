# PRD: AI Metadata Generation for Training Video Transcripts

## Problem Statement

After transcribing a training video with Whisper, the user is left with a raw transcript but no structured metadata. Manually writing a title, description, tags, learning goals, and skills covered is time-consuming and inconsistent. There is no automated way to extract this information from a transcript and present it in a machine-readable format that downstream systems (LMS, CMS, search index) can consume.

Whisper cannot solve this task. It is a speech-recognition model whose decoder is conditioned on audio features — it can only generate text that represents what was said in an audio input. It cannot accept a text transcript and produce a summary, classification, or structured output from it. A separate, general-purpose LLM is required for this step.

## Solution

A standalone post-processing script (`analyze.py`) accepts a training video transcript (from a file or stdin) and calls a locally running Ollama model to extract structured metadata. The script outputs a JSON object containing a title, description, tags, goals, and skills. It runs after `infer.py` or `infer-full.py` as a distinct step, keeping transcription and metadata generation cleanly separated.

## Pipeline Position

```
audio file
    │
    ▼
infer.py  ──►  transcript (text)
                    │
                    ▼
              analyze.py  ──►  metadata (JSON)
```

`analyze.py` is backend-agnostic with respect to how the transcript was produced — it can consume the output of any transcription tool, not only the Whisper scripts in this project.

## User Stories

1. As a content producer, I want to pass a transcript file to a script and receive structured metadata in JSON, so that I can populate a learning management system without writing metadata by hand.
2. As a developer, I want to pipe the output of `infer.py` into `analyze.py`, so that I can run transcription and metadata generation in a single shell pipeline without a temporary file.
3. As a developer, I want the metadata to include a concise title, so that the video has a human-readable name without manual effort.
4. As a developer, I want the metadata to include a 2-3 sentence description, so that a viewer can decide whether the video is relevant to them before watching.
5. As a developer, I want the metadata to include a list of tags, so that the video can be indexed and searched by keyword.
6. As a developer, I want the metadata to include a list of learning goals, so that learners know what they will be able to do after watching the video.
7. As a developer, I want the metadata to include a list of skills covered, so that the video can be associated with competency frameworks or skill taxonomies.
8. As a developer, I want all five metadata fields to be present in every response, so that downstream consumers do not need to handle missing keys.
9. As a developer, I want the model to be configurable via a `--model` flag, so that I can swap between llama3, mistral, or any other locally available Ollama model without changing code.
10. As a developer, I want llama3 to be the default model, so that the script works out of the box on a standard Ollama installation.
11. As a developer, I want to read the transcript from stdin using `-` as the file path, so that I can pipe transcription output directly without saving a file.
12. As a developer, I want clear error messages if Ollama is not running, so that I can diagnose connection problems immediately.
13. As a developer, I want clear error messages if the model returns malformed JSON, so that I know when the output is unusable.
14. As a developer, I want the script to exit with a non-zero code on any failure, so that shell pipelines and CI workflows detect errors correctly.
15. As a developer, I want the JSON output to be pretty-printed, so that it is human-readable in a terminal.
16. As a content producer, I want the metadata to reflect the actual content of the transcript, not a generic template, so that generated tags and goals are specific and useful.
17. As a developer, I want the script to have no dependency on any cloud API or API key, so that it works in air-gapped or restricted HPC environments.
18. As a developer, I want the script to be independent of `infer.py` and `train.py`, so that I can use it on any plain-text transcript regardless of how it was produced.
19. As a developer, I want an empty transcript to produce an error rather than nonsense metadata, so that I don't silently receive garbage output.

## Implementation Decisions

### Modules

- **`analyze.py`** — standalone script. Accepts `--transcript` (file path or `-` for stdin) and `--model` (default `llama3`). Reads the transcript, constructs a structured prompt, calls the Ollama `/api/generate` endpoint, parses the JSON response, and prints it to stdout.

### Key architectural decisions

- **Separate script, not integrated into `infer.py`** — metadata generation is a distinct concern. Keeping it separate means transcripts can be re-analysed without re-running Whisper, the script can be tested independently, and it works on transcripts from any source.
- **Local Ollama model, no cloud API** — calls `http://localhost:11434/api/generate`. No API key required. Works in air-gapped environments. Uses the `requests` library.
- **`format: "json"` Ollama parameter** — instructs Ollama to constrain output to valid JSON. The prompt additionally carries the target schema to guide field names and types.
- **Stdin fallback via `-` convention** — if `--transcript -` is passed, the script reads from `sys.stdin`. Otherwise it opens the named file.

### JSON output schema

```json
{
  "title": "string",
  "description": "string (2-3 sentences)",
  "tags": ["string", "..."],
  "goals": ["string", "..."],
  "skills": ["string", "..."]
}
```

### Error handling

| Failure condition | Behaviour |
|---|---|
| Ollama not running (`ConnectionError`) | Print message directing user to `ollama serve`, exit 1 |
| Ollama HTTP error | Print status code and message, exit 1 |
| Model returns invalid JSON | Print raw response for debugging, exit 1 |
| Empty transcript | Print error, exit 1 |

### Default model

`llama3` (8B). Adequate for metadata extraction on short-to-medium transcripts. Swap via `--model mistral` or any other model available in the local Ollama installation.

## Testing Decisions

- **What makes a good test:** test the externally observable behaviour of each function. Given a known transcript string, assert that the prompt is constructed correctly and the JSON output matches the expected schema. Do not test Ollama internals or model weights.
- **Modules to test:**
  - Prompt construction — given a transcript, assert the prompt contains the transcript text and the schema description.
  - `analyze()` function — mock the HTTP call to Ollama, return a known JSON string, assert the function returns the correct dict with all five keys.
  - Error paths — mock `ConnectionError` and assert exit code 1; mock a non-JSON response and assert exit code 1; pass an empty transcript and assert exit code 1.
  - Stdin path — pass `-` as `--transcript` and monkeypatch `sys.stdin` with a known string.
- **Approach:** mock at the HTTP boundary (`requests.post`), not inside Ollama or the model itself.

## Out of Scope

- Metadata in languages other than English — output is always English regardless of transcript language.
- Persisting metadata to a database, file, or external API — stdout only; the caller handles routing.
- A `--output` flag for writing directly to a file — shell redirection (`> metadata.json`) covers this for now.
- Fine-tuning any model on training-video metadata.
- Batch processing of multiple transcripts in a single command.
- Video file input — the script operates on text transcripts only.
- Confidence scoring or ranking of generated metadata.
- Schema validation beyond JSON parsing — field presence is assumed from the prompt.
- A web UI or API server wrapping `analyze.py`.

## Further Notes

- The `format: "json"` Ollama parameter constrains output to valid JSON but does not guarantee schema compliance. If schema drift becomes a problem (missing keys, wrong types), a lightweight validation step checking that all five keys are present can be added before printing.
- The Ollama HTTP API is the only backend-specific component. If Ollama is unavailable in a given environment, the `call_ollama()` function can be replaced with a call to any other local inference server (llama.cpp HTTP, vLLM, etc.) without changing the rest of the script.
- For very long transcripts (>10k tokens), a model with a larger context window (e.g. `llama3:70b` or `mistral`) may produce better coverage than the default `llama3` 8B model.
- Metadata is always generated in English, even when the transcript is in Spanish, French, Mandarin, or Arabic. This is intentional — the target consumers (LMS, CMS) are assumed to be English-language systems.
