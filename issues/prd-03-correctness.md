# PRD 03: Correctness — Logic Bugs Hiding Behind Green Tests

**Parent PRD:** `prd/task-2-company-brain/prd.md`
**Source:** Codebase review, 2026-09-29. All `file:line` citations were verified against the working tree on that date and will drift — re-verify before acting on any single line.
**Pass:** 3 of 4. Companions: [01 Stop the Bleeding](prd-01-stop-the-bleeding.md) · [02 Reclaim the Allocation](prd-02-reclaim-allocation.md) · [04 Trustworthiness](prd-04-trustworthiness.md)

**Size note:** this is the largest pass, roughly three times the others, and it mixes genuine logic bugs with consolidation debt. It is organised into five groups (A–E) so it can be split at a group boundary if review capacity is short. Groups A and C are the ones that change behaviour users can observe; B, D, and E are correctness-and-hygiene.

---

## Problem Statement

The test suite is green — 96 Python tests plus 7 bats tests, most of them genuinely good. And yet a review found roughly thirty defects the suite does not catch, including several that are actively misleading. The characteristic pattern is a function whose output shape is asserted but whose output content is not, and a test that names a scenario it does not actually create.

The clearest example: the sentiment module chunks transcripts at 200 words with a comment explaining that this is comfortably within the model's token limit, and then truncates each chunk to 400 *characters* — roughly 100 tokens. A 200-word chunk is around 1,200 characters. Two-thirds of every transcript never reaches the model, and the per-video aggregate is computed over prefixes. The comment and the code contradict each other on adjacent lines, and no test asserts on chunk length.

Second: the graph builder derives node identity from a file's basename. `en/interview.mp3` and `es/interview.mp3` collapse into a single node. The same basename-matching flaw in the playlist generator means a user who has watched one video in one language is silently excluded from every same-named video in all others. The knowledge graph — the headline deliverable of Task 2 — merges distinct content across languages without complaint.

Third: a dead code path with a test pointed at it. The playlist builder hardcodes `preferred_sentiment=None`, so the sentiment bonus in the scoring function is unreachable from the production entry point. The test for that function calls the scoring function directly, so it passes. The test gives confidence in a path nothing uses, and the preference field is never read from a user profile.

Fourth: the graph builder interpolates LLM-generated titles and tags into HTML and into an inline `<script>` block via raw string formatting, with no escaping. The model output is untrusted input to a page that gets opened in a browser.

Fifth: a field called `uploaded_by` is rendered as a filter dropdown in the graph viewer, read by two modules, and specified in the parent PRD's Qdrant schema — and **nothing in the pipeline ever writes it.** The filter is permanently empty and always will be.

Sixth: `pipeline.yaml` lists the language `zh`. The training script, the training job, the README, and the actual `checkpoints/` directory all say `zh-CN`. In whole-inbox scan mode the pipeline looks for `checkpoints/zh`, does not find it, and skips every Chinese file with an error. Three-way disagreement on a single string.

Seventh: the embed service reports `{"status": "ok"}` unconditionally, and only loads its model inside the CLI entrypoint. Under any WSGI server the entrypoint never runs, the model stays `None`, `/embed` returns a 500 from an `AttributeError` — and `/health` still says ok. The health check is what the deployment waits on.

And the determinism guarantee that `index_server.py` is careful about in a comment — `uuid5` point IDs so re-runs upsert rather than duplicate — is undermined by a fallback that generates a random ID when `video_id` is missing. The comment and the code disagree about the same line.

---

## Solution

Five groups of work, each independently mergeable.

**Group A — Pipeline data correctness.** Fix the sentiment truncation so the full chunk reaches the model. Reconcile `zh` / `zh-CN` across all four locations. Add `truncation=True` to the trainer's label tokenization, which is currently missing and silently produces unusable label sequences for long utterances. Fix the sentiment result not appearing in the on-disk analysis file. Make the sentiment label lookup total rather than raising on an unknown label. Record when a transcript was truncated. Disambiguate output stems so two files with the same stem in one language do not overwrite each other.

**Group B — Graph and playlist correctness.** Make node identity language-qualified so cross-language content does not merge. HTML-escape the graph template. Either wire `uploaded_by` through the pipeline or remove it from the schema, the reader, and the filter UI — it is currently a filter that can never match anything. Either read `preferred_sentiment` from the profile or delete the unreachable branch *and its test*, which currently manufactures false confidence. Make the watch-history exclusion language-aware.

**Group C — Service hardening.** Make `/health` reflect actual model state, and load the model at import time so it works under any WSGI server. Validate request bodies and return 400 instead of 500. Bound the embed batch. Assert vector dimensionality against the configured dimension. Remove the random-ID fallback that breaks idempotency. Replace the bare `except` in collection setup, which makes a connection failure indistinguishable from a missing collection. Note in the code that the Werkzeug development server is not a production server.

**Group D — Consolidation.** Collapse three near-duplicate inference modules into one. Cache the Whisper pipeline instead of rebuilding it per call. Stop `--segments` writing outputs into the audio input directory. Extract the four copies of the host/port parser and the duplicated collection-name constants into one module. Make search call the embed service rather than reloading the model it exists to serve.

**Group E — Environment and CLI.** Define the Docker host alias the local pipeline depends on. Fix argument quoting through the Singularity `bash -c` boundary in the graph job, which currently loses all quoting for user-supplied values. Sanitise the user-supplied value that is interpolated into an output path.

---

## User Stories

### Group A — Pipeline data correctness

1. As a user reading sentiment scores, I want the score to reflect my whole video, so that the number means something.
2. As a user reading sentiment scores, I want every chunk of my transcript to be classified, so that a positive conclusion in minute forty is not discarded.
3. As a developer, I want the chunk size and the truncation limit to be the same number, so that the code cannot contradict its own comment.
4. As a developer, I want a test that asserts the full chunk text reaches the classifier, so that silent content loss is caught.
5. As an operator, I want the pipeline to process Chinese files, so that the `zh-CN` language actually works.
6. As an operator, I want one spelling of the Chinese language code across config, training, and docs, so that I do not have to remember which file uses which.
7. As an operator, I want a missing checkpoint to name the exact directory it looked for, so that I can see the mismatch rather than guess at it.
8. As a developer, I want long FLEURS utterances to be truncated explicitly during tokenization, so that label sequences are always within the decoder limit.
9. As a developer, I want a test asserting label token lengths are within the model limit, so that the missing truncation cannot return.
10. As a user, I want the sentiment label and score in the on-disk analysis file, so that the local file and the indexed record agree.
11. As a developer, I want an unrecognised sentiment label to degrade to neutral rather than raise, so that an upstream model change does not crash the pipeline.
12. As a user, I want to know when a long video's metadata was extracted from only part of the transcript, so that I do not over-trust a summary.
13. As a user with both an `.mp3` and an `.mp4` of the same content, I want them processed without overwriting each other, so that I do not silently lose one.
14. As a developer, I want the WER metric resolved once rather than per epoch, so that evaluation does not re-load it on every call.
15. As a developer, I want dead device-detection code removed, so that I do not think MPS is supported when it is not used.
16. As a developer, I want training hyperparameters exposed as flags, so that I can tune the run without editing code.

### Group B — Graph and playlist correctness

17. As a user viewing the knowledge graph, I want the Spanish and English versions of a video to be distinct nodes, so that cross-language content does not silently merge.
18. As a user viewing the knowledge graph, I want node labels escaped, so that a transcript containing markup does not break the page.
19. As a user opening the graph in a browser, I want generated text to be rendered as text, so that model output cannot inject content into my page.
20. As a user, I want the "Uploaded by" filter to either work or not be shown, so that I am not offered a filter that can never match.
21. As an operator, I want `uploaded_by` populated during ingestion if the PRD requires it, so that the filter has data behind it.
22. As a user, I want my playlist to respect my preferred sentiment, so that onboarding content is not filtered by a hardcoded default.
23. As a developer, I want unreachable scoring branches removed, so that I do not maintain code nothing calls.
24. As a developer, I want tests to exercise the code path production actually takes, so that a passing suite means something.
25. As a user, I want watching a video in one language not to exclude it in every other language, so that my history reflects what I actually watched.
26. As a user, I want watch history matched by language and file, so that exclusions are precise.
27. As a developer, I want the scoring weights configurable and commented, so that the ranking is not a set of unexplained magic numbers.
28. As an operator, I want the graph builder to remain usable as the corpus grows, so that it does not become quadratic against a real library.
29. As a developer, I want one metadata loader rather than two near-identical ones, so that a schema change is made in one place.
30. As a user, I want colours defined once, so that the JSON export and the HTML viewer cannot disagree.

### Group C — Service hardening

31. As an operator, I want `/health` to report a real failure when the model is not loaded, so that a broken service is not treated as ready.
32. As an operator, I want the deploy to wait for a genuinely healthy service, so that the pipeline does not start against a service that will 500.
33. As a developer, I want the model loaded at import time, so that the service works under any WSGI server rather than only when run as a script.
34. As an API consumer, I want a malformed request to return 400 with a useful message, so that I can tell my bug from the server's.
35. As an API consumer, I want a missing field to be rejected explicitly, so that I do not get an opaque 500 from a `KeyError`.
36. As an operator, I want an empty `video_id` rejected, so that I do not get colliding deterministic point IDs.
37. As an operator, I want the embed service to bound its batch size, so that one three-hour video cannot exhaust server memory.
38. As a developer, I want vector length validated against the configured dimension, so that a model swap fails loudly at startup rather than mysteriously at query time.
39. As a developer, I want the dimension declared in one place, so that embed and index cannot disagree.
40. As an operator, I want re-indexing to be idempotent even when `video_id` is absent, so that the documented guarantee holds unconditionally.
41. As a developer, I want a Qdrant connection failure distinguished from a missing collection, so that the error message is actionable.
42. As a reviewer, I want the use of a development server in a long-running role documented, so that it is a known limitation rather than an accident.

### Group D — Consolidation

43. As a developer, I want one inference module rather than three near-identical ones, so that a fix applies everywhere.
44. As a developer, I want the interactive demos to run the same code as the production pipeline, so that what I test is what runs.
45. As an operator, I want the Whisper model loaded once per task rather than once per file, so that a large batch is not dominated by model loading.
46. As an operator, I want inference outputs written to the results directory rather than the input directory, so that the inbox stays clean.
47. As a developer, I want one host/port parser rather than four copies, so that a fix applies everywhere.
48. As a developer, I want one definition of the collection names and the embedding model, so that a rename is a one-line change.
49. As an operator, I want search to use the running embed service, so that the GPU model is loaded once for the whole system.
50. As a developer, I want the orchestrator to use a public interface from the sentiment module rather than its private helper, so that refactoring the module does not break the caller.

### Group E — Environment and CLI

51. As a developer on Linux, I want the local Docker pipeline to reach the host services, so that the documented command works on the platform LUMI developers use.
52. As a developer, I want service URLs to be configured one way rather than two, so that I can find where to change them.
53. As a developer, I want a user name containing a space or punctuation to reach the playlist generator intact, so that real names work.
54. As a developer, I want a user name to be unable to write outside the output directory, so that a malformed argument cannot traverse paths.
55. As a developer, I want a malformed flag to fail loudly rather than being silently dropped, so that typos are caught.

---

## Implementation Decisions

### Group A — Pipeline data correctness

**Sentiment chunking — `5-sentiment/sentiment.py`.** The module declares a 200-word chunk size with a comment justifying it against the model's limit (line 29), then truncates each chunk to 400 characters (line 82-83). 400 characters is roughly 100 tokens; a 200-word chunk is roughly 1,200 characters. Resolve in favour of the model's actual limit: the chunk size becomes the single source of truth, and any per-input cap is derived from it rather than hardcoded. If a hard cap is genuinely needed to avoid tokenizer warnings, it must be expressed in tokens or derived from the chunk size — not as an independent magic number. The model label lookup (line 96) becomes a total lookup that degrades to neutral for an unrecognised label rather than raising.

**`zh` / `zh-CN` reconciliation.** Four locations disagree: `pipeline.yaml:15` says `zh`, `1-train/train.py:29,37` and `1-train/hpc/train-sbatch-gpu.sh:35` say `zh-CN`, `README.md:78` says `checkpoints/zh`, and the directory on disk is `checkpoints/zh-CN`. Pick the FLEURS/HuggingFace code form, since that is what the training data uses, and apply it to all four. Add a test that asserts every configured language has a corresponding checkpoint directory and inbox subdirectory, which makes the class of mismatch self-detecting.

**Trainer label truncation — `1-train/train.py:67`.** Tokenization omits `truncation=True`. Whisper's decoder has a 448-token limit and the collator does not truncate, so any utterance exceeding it produces a label sequence the model cannot consume. This is silent data corruption at the tail of long samples. Add `truncation=True`, and add a test asserting tokenised label lengths are within the decoder limit. Hoist the `evaluate.load("wer")` call (line 99) out of the per-epoch metric function, which currently re-resolves it on every evaluation. Remove the unused device-detection branch (lines 149-152) — `use_mps` is computed and never used.

**Sentiment in the analysis file — `pipeline.py:242,253-254`.** The analysis file is written *before* the sentiment result is merged into the metadata dict, so the on-disk JSON never contains the label or score even though the Qdrant payload does. Move the write after the merge, or write the file once at the end of the stage sequence.

**Truncation marker — `3-analyze/analyze.py`.** The transcript is capped at 3,000 words, and the emitted metadata does not record that this happened. The prompt mentions it, but the model may not echo it. Add an explicit field so a consumer can tell a complete extraction from a partial one.

**Stem collisions — `pipeline.py:191`.** Output paths derive from the file stem, so `a.mp3` and `a.mp4` in the same language directory write identical outputs while producing distinct `.done` sidecars. Either include the extension or a content hash in the output stem, or detect the collision and error.

**Flag surface — `1-train/train.py`.** `batch_size` and `epochs` are exposed; `num_proc` is hardcoded (line 144), and `warmup_steps`, `gradient_accumulation_steps`, and `dataloader_num_workers` are not exposed at all. Expose them for parity with the rest of the training configuration.

### Group B — Graph and playlist correctness

**Node identity — `9-graph/graph.py:63`.** Node IDs are file basenames, so identically-named files across languages merge. Qualify the ID with the language, and apply the same fix to the watch-history matching in `9-graph/playlist.py:153,174`, where the identical flaw means a watched filename is excluded in every language.

**Template escaping — `9-graph/graph.py:107-108,112`.** Option values are built by raw string interpolation of Qdrant payload fields, and the graph JSON is inlined raw into an inline `<script>` block. Both take LLM-generated content. Escape all interpolated values for their context — attribute values for HTML, and a safe serialisation for script content that cannot terminate the block. Node colours are hardcoded in the Python (lines 21-26) and again in the template; define once.

**`uploaded_by`.** Read by `graph.py:70,105` and `playlist.py:123`, rendered as a filter in `graph_template.html:44-47,73,144`, and specified in the parent PRD's Qdrant schema — but no writer exists anywhere in the pipeline. The parent PRD treats it as a required field and `Task-2.md` describes contributor analytics built on it, so **wiring it through ingestion is the recommended path**, with ingestion deriving it from the sync manifest. If it cannot be sourced, it must be removed from the schema, the reader, and the filter UI in the same change — a filter that can never match is worse than no filter.

**Unreachable sentiment branch — `9-graph/playlist.py:180`.** `build_playlist` hardcodes `preferred_sentiment=None`, so the sentiment bonus in `score_candidates` (lines 106-108) is dead in production. The profile field exists and is never read. Read it from the profile, and make the `--sentiment` flag's meaning consistent with the module docstring, which describes a preference while the implementation applies it as a filter. **Delete the test that gives false confidence** (`9-graph/test_playlist.py:95-101`) or rewrite it to go through `build_playlist`.

**Scoring and graph scale — `9-graph/playlist.py:110`, `graph.py:78-79`.** The weights (0.5 role / 0.4 history / 0.1 sentiment) are unexplained magic numbers; move them to configuration with a comment justifying each. Tag-overlap edge building is O(n²) over all videos, which is acceptable at demo scale and will not survive a real corpus; note the ceiling and leave the optimisation out of scope rather than pretending it does not exist.

**Loader duplication.** `load_metadata` (`graph.py:39-55`) and `load_all_metadata` (`playlist.py:67-82`) are near-identical. Extract one.

### Group C — Service hardening

**Health and model lifecycle — `6-embed/embed_server.py:25-27,60,68`.** `/health` returns ok unconditionally, and the model is assigned inside the CLI entrypoint, so under any WSGI server it stays `None`, `/embed` fails with an `AttributeError`-derived 500, and `/health` still reports ok. Load the model at import time and have `/health` reflect its actual state. The index server's `/health` has the same shape: it checks Flask liveness only, so a server wired to a dead Qdrant reports healthy.

**Request validation.** Neither service validates its input. `request.get_json(force=True)` followed by direct key access yields a 500 from a `KeyError`; an empty `video_id` is silently accepted and produces deterministic-but-colliding point IDs. Validate and return 400 with a specific message.

**Idempotency — `7-index/index_server.py:95-97`.** The code falls back to a random UUID when `video_id` is missing, which destroys the `uuid5` guarantee the adjacent comment describes. Reject the request instead of guessing.

**Bounded embedding — `6-embed/embed_server.py:44`.** The batch is unbounded. A long video produces thousands of chunks in one request and one encode call, and the orchestrator allows 600 seconds for it. Cap the batch and chunk the work.

**Vector dimension — `7-index/index_server.py:25`.** The dimension is hardcoded and the embed service never asserts its model's output size, so swapping the embedding model breaks indexing silently. Declare the dimension once, share it, and validate incoming vector length.

**Collection setup — `index_server.py:33-42`.** A bare `except Exception` makes a connection failure indistinguishable from a missing collection; the subsequent create then fails with a confusing traceback. Narrow the exception, and detect a pre-existing collection with the wrong dimensionality.

**Development server.** Both services run Werkzeug's development server bound to all interfaces as a long-running service on a shared cluster node. Replacing it is a larger deployment change; this pass documents the limitation clearly in the code so it is a known decision rather than an oversight.

**Payload size.** The orchestrator POSTs full 1024-float vectors to the index server, which forwards them to Qdrant — roughly 2.5 MB of decimal float JSON per hour of video. The request-size ceiling that bounds this is duplicated between the HPC and Docker configs; extract the constant. (The ceiling itself is a PRD 02 item.)

### Group D — Consolidation

**Inference modules.** `2-inference/infer.py`, `infer-full.py`, and `infer-30-secs.py` are three near-identical files. Only `infer.py` has segment support, and it is the one the orchestrator imports — but the HPC interactive scripts invoke `infer-full.py`, so the demos and production run different code. Collapse to one module; the segment support becomes the only path. While doing so, fix two behaviours: the Whisper pipeline is reconstructed on every call (lines 36-43) rather than cached, which is expensive across a batch; and `--segments` writes its outputs into the audio file's own directory (lines 87-89), which for pipeline inputs is the inbox.

**Shared helpers.** `_parse_host_port` is copy-pasted four times (`7-index/index_server.py:105`, `8-search/search.py:22`, `9-graph/graph.py:32`, `9-graph/playlist.py:43`). The embedding model name and collection names are duplicated across three modules. Extract into one shared module that all four consumers import.

**Search must use the service — `8-search/search.py:33`.** The model is reloaded inside `search()` on every call, bypassing the entire architectural point of the embed server, whose docstring states that it loads the model once. Either POST to `/embed` or cache the model at module level. Prefer the service: it is already running on a GPU node.

**Private cross-module import — `pipeline.py:97`.** The orchestrator reaches into the sentiment module's private helper to get the chunk splitter. Expose a public interface.

### Group E — Environment and CLI

**Docker host alias.** `pipeline-docker.sh:13` passes a host alias for Ollama that no service defines in `docker-compose.yml`. It resolves on Docker Desktop and fails on native Linux, which is the platform LUMI developers actually use. Define the alias on the relevant service. While there, note that the Ollama URL arrives by CLI flag while the embed and index URLs arrive by environment variable — two mechanisms for one concern.

**Argument quoting — `9-graph/hpc/graph-sbatch.sh:122`.** An argument array is expanded into a double-quoted `bash -c` string that an inner shell re-parses, so all quoting is lost. A user name containing a space, a glob, or a semicolon breaks the argument list. Pass the array through so the inner shell receives it as positional parameters.

**Path construction — `graph-sbatch.sh:68`.** A user-supplied value is interpolated into an output path, so a slash or a dot-dot produces an unexpected path. Sanitise it. The local sibling `create-playlist-graph.sh` handles the same logic correctly and is the reference.

### Deliverables

| # | Deliverable | Group | Description |
|---|---|---|---|
| 1 | Sentiment truncation fix | A | Chunk size becomes the single source of truth; no independent char cap |
| 2 | Total sentiment label lookup | A | Unknown label degrades to neutral instead of raising |
| 3 | Language code reconciliation | A | One spelling across config, training, docs, and disk |
| 4 | Checkpoint/language consistency test | A | Every configured language has a checkpoint and an inbox dir |
| 5 | Trainer `truncation=True` | A | Label sequences bounded by the decoder limit |
| 6 | Trainer token-length test | A | Asserts labels never exceed the limit |
| 7 | Sentiment in analysis file | A | Written after the metadata merge |
| 8 | Transcript truncation marker | A | Metadata records that extraction was partial |
| 9 | Stem collision fix | A | Two files with one stem do not overwrite each other |
| 10 | Trainer cleanup | A | Hoist metric load, remove dead MPS branch, expose flags |
| 11 | Language-qualified node IDs | B | Cross-language files no longer merge |
| 12 | Language-aware watch history | B | Exclusion matches the right file in the right language |
| 13 | Template escaping | B | HTML and script contexts escaped for generated content |
| 14 | `uploaded_by` wired or removed | B | Populated at ingestion, or removed from schema, reader, and UI |
| 15 | Sentiment preference honoured | B | Profile field read; dead branch and its test resolved |
| 16 | Scoring weights configured | B | Moved out of code with justification |
| 17 | Metadata loader deduped | B | One loader, not two |
| 18 | Colour single-sourced | B | Defined once for both JSON and HTML |
| 19 | Real `/health` | C | Reflects model state; works under any WSGI server |
| 20 | Model loaded at import | C | Decoupled from the CLI entrypoint |
| 21 | Request validation | C | 400 with specific messages instead of 500 from `KeyError` |
| 22 | Empty `video_id` rejected | C | No more deterministic-but-colliding IDs |
| 23 | Random-ID fallback removed | C | `uuid5` idempotency holds unconditionally |
| 24 | Bounded embed batch | C | Capped and chunked |
| 25 | Vector dimension shared and validated | C | One declaration; mismatch fails loudly |
| 26 | Collection setup exceptions narrowed | C | Connection failure distinguishable from missing collection |
| 27 | Dev-server limitation documented | C | Recorded in code as a known decision |
| 28 | Single inference module | D | Three files collapsed to one |
| 29 | Whisper pipeline cached | D | Loaded once per task, not once per file |
| 30 | Segments output relocated | D | Written to results, not the inbox |
| 31 | Shared host/port parser | D | Four copies → one module |
| 32 | Shared constants | D | Model name and collection names defined once |
| 33 | Search uses the embed service | D | No per-query model reload |
| 34 | Public sentiment interface | D | No private cross-module import |
| 35 | Docker host alias defined | E | Local pipeline works on Linux |
| 36 | Service URL config unified | E | One mechanism, not two |
| 37 | Graph job argument quoting | E | User names with spaces survive |
| 38 | Output path sanitised | E | No traversal from a user-supplied value |

---

## Testing Decisions

A good test asserts on **observable output**, not internal structure. The theme of this pass is that the existing tests assert shape and miss content — so the new tests must assert on content, and must set up the scenario their name claims.

**Prior art:** `5-sentiment/test_sentiment.py` patches the module-level classifier getter with a `MagicMock` and asserts on the returned dict — the right seam. `2-inference/test_infer.py` tests segment extraction including the `None`-timestamp case. `7-index/test_index_server.py` exercises the Flask test client. Reuse all three patterns.

**A no-op test must be fixed first — `5-sentiment/test_sentiment.py:115-130`.** The test named "majority label wins" sets `side_effect` to a list of three single-item responses, but `run_sentiment` makes one call with all three texts. Only the first response is consumed, so exactly one chunk is classified and the majority path is never taken. The assertion passes for the wrong reason. Rewrite it to drive the actual per-chunk behaviour, and confirm it fails when the majority logic is broken.

**New tests, by group:**

*A* — a test asserting the full chunk text reaches the classifier (fails against current code); a language-consistency test asserting every configured language has both a checkpoint directory and an inbox subdirectory; a trainer test asserting tokenised label lengths are within the decoder limit (fails against current code); an assertion that the analysis file contains the sentiment fields; a test that two same-stem files produce distinct outputs; a test that an unrecognised sentiment label degrades rather than raises.

*B* — a test that two same-named files in different languages produce two distinct graph nodes (fails against current code); a test that a title containing `<` and a transcript containing `</script>` render as text; a test that watching a video in one language does not exclude it in another; a test that `build_playlist` honours a profile's preferred sentiment, replacing the direct `score_candidates` call at `test_playlist.py:95-101`.

*C* — a test that `/health` reports unhealthy when the model is `None`; tests that a missing field, a malformed body, an empty `video_id`, and a wrong-length vector each return 400; a test that omitting `video_id` is rejected rather than given a random ID — **this one matters because the `uuid5` idempotency guarantee is currently unprotected by any test, and a regression to `uuid4` would stay green**; a test that collection setup distinguishes a connection failure from a missing collection.

*D* — a test asserting the inference module is not reloaded per file; a test asserting segment output lands in the results directory and not the inbox.

*E* — bats assertions that the graph job passes a name containing a space through to the inner shell intact, and that a `..` in the user argument cannot escape the output directory.

**Tests that must be updated rather than added:** `5-sentiment/test_sentiment.py:115-130` (above); `3-analyze/test_analyze.py`, whose four `SystemExit` assertions lock in the exact behaviour PRD 01 changes; `9-graph/test_graph.py:176`, which asserts a JavaScript identifier is present in the template and couples the test to a variable name rather than to behaviour.

**Not tested here:** graph rendering in a browser, real Qdrant behaviour beyond the mocked client, and actual Docker Compose networking. Those are verified by running the system.

---

## Out of Scope

- **The full-vector JSON round-trip redesign.** The payload-size ceiling is extracted as a constant here and its HPC/Docker duplication is fixed in PRD 02, but changing the wire format to a more efficient encoding is a larger change with cross-service coordination.
- **Replacing the Werkzeug development server.** Documented as a known limitation (deliverable 27), not fixed. Doing so properly means choosing a WSGI server, configuring timeouts and limits, and revisiting the exposure of the services on a shared node.
- **The O(n²) graph build optimisation.** Recorded, not fixed. It is not a bottleneck at demo scale.
- **Authentication or authorisation on the services.** Worth raising for a shared cluster — any user on the relevant partition can currently reach them. This is a deployment-hardening decision that needs a threat model, not a bug fix.
- **Autolabelling and the `label.py` module.** Referenced throughout the older issue files and removed from the tree with no replacement. If it is wanted, it is a new feature.
- **Adopting the larger-context model** proposed in `issues/008-larger-context-model.md`. The truncation marker from Group A is designed to be useful either way, but the model swap is a separate decision.
- **Everything in PRD 01.** In particular, whether a file is flagged `.done` when sentiment fails is a failure-semantics question, not a correctness one — even though the sentiment truncation is fixed here.
- **The broken demo scripts.** `pipeline-demo-local.sh` and `pipeline-demo-local-docker.sh` reference files that do not exist. That is documentation drift as much as broken code, and it is scheduled with the documentation work in PRD 04.
- **Test suite breadth and CI.** Several existing tests need rewriting rather than the suite needing to grow; the general coverage and CI gap is PRD 04.

---

## Further Notes

- **The sentiment truncation is the highest-value fix in this pass** and the cheapest. One number is wrong on one line, and it silently affects every sentiment score the system has ever produced. Any sentiment output generated before this fix should be considered unreliable.
- **`uploaded_by` has a decision attached, not just a fix.** The parent PRD specifies it as a required field, and `Task-2.md` builds contributor analytics on top of it. Deleting it to make the warning go away would be removing a specified feature. Sourcing it from the sync manifest is the path that preserves the PRD's intent — but it is a product decision, not a bug fix, and it should not be made silently inside a cleanup pass.
- **The `uuid5` determinism is one of the better engineering decisions in the repository** — deterministic point IDs so re-runs upsert instead of duplicating, with the reasoning written next to it. It is also completely untested, and undermined by a fallback three lines below the comment. A regression to `uuid4` would pass the entire suite.
- **Three near-duplicate inference modules is a symptom, not the disease.** The disease is that there is no shared-constants module, so the model name, collection names, and host parser are copy-pasted into every consumer. Fixing the three files without fixing the cause means the next rename does the same damage again. Do Group D's extraction and the collapse together.
- **Two of the strongest patterns in this repository are the ones being preserved here:** the E5 `passage:` and `query:` prefixes are handled correctly *and* covered by tests, and `3-analyze/analyze.py:7-17` documents the context-window truncation arithmetic in a comment that a human clearly reasoned through. The sentiment bug is instructive precisely because it is the same kind of comment — the reasoning is there, and the code does not match it. When in doubt, trust the comments in this repo; they are usually describing intent that the code has drifted from.
- **Group E is small but blocks local testing.** Neither the Docker host alias nor the broken demo scripts affect production, but both mean a developer cannot verify anything locally without hand-patching. That is friction on every future change to this codebase, which is why it is worth doing even though nothing is user-visible.
- **This pass touches `pipeline.py` and `pipeline-hpc-sbatch.sh` in common with PRD 01.** Sequencing matters: PRD 01 first, since its `.done` semantics determine what this pass's analysis-file and truncation-marker fields actually persist. Both PRDs will conflict on the same hunks; expect to rebase.
