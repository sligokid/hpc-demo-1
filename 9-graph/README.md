# 9-graph — Knowledge Graph & Playlist Generator

Query-layer tools that read from the `video_metadata` Qdrant collection and produce usable outputs with no additional model inference.

---

## Files

| File | Description |
|---|---|
| `graph.py` | Exports `graph.json` (nodes + edges) and `graph.html` (D3.js viewer) |
| `graph_template.html` | HTML/JS template rendered by `graph.py` with inline graph data |
| `playlist.py` | Generates a ranked personalised playlist for a given user profile |
| `create-playlist-graph.sh` | Local runner — activates the venv and runs `graph.py` + `playlist.py` |
| `hpc/graph-sbatch.sh` | SLURM batch job — runs the same steps inside Singularity on LUMI |
| `test_graph.py` | Unit tests for `graph.py` |
| `test_playlist.py` | Unit tests for `playlist.py` |

Supporting files in the project root:

| File | Description |
|---|---|
| `roles.yaml` | Role → tag mapping used by `playlist.py` for relevance boosting |
| `profiles/<user>.json` | Per-user profile: role, language, watch history, opt-out flag |

---

## Prerequisites

Qdrant must be running and the `video_metadata` collection must be populated by the pipeline before running either tool.

```bash
docker run -p 6333:6333 qdrant/qdrant
```

---

## Running on LUMI (HPC)

Use `hpc/graph-sbatch.sh` instead of `create-playlist-graph.sh`. It reads the Qdrant endpoint written by the `D-qdrant` service job and runs both Python scripts inside the project's Singularity container.

**Prerequisites:** `D-qdrant` service must be running and have written `$SCRATCH/qdrant.endpoint`.

```bash
# Default — user engineer@org.com, top 10
sbatch 9-graph/hpc/graph-sbatch.sh

# Custom user / playlist size
sbatch 9-graph/hpc/graph-sbatch.sh --user operative@org.com --top-n 5

# Sentiment filter
sbatch 9-graph/hpc/graph-sbatch.sh --user engineer@org.com --sentiment positive

# EU AI Act opt-out
sbatch 9-graph/hpc/graph-sbatch.sh --no-personalise --user manager@org.com
```

Outputs land in `sync/output/` (same as the local script):

| Output | Description |
|---|---|
| `sync/output/graph.json` | Graph nodes and edges |
| `sync/output/graph.html` | Self-contained D3.js viewer |
| `sync/output/playlist-<user>.json` | Ranked playlist for the requested user |

Logs go to `logs/graph-slurm-<jobid>.out`.

---

## graph.py

Reads every record from `video_metadata` and produces:

- **`graph.json`** — nodes (one per video) and edges (one per pair of videos that share at least one tag). Edge weight = number of shared tags.
- **`graph.html`** — self-contained D3.js force-directed viewer. Opens directly in a browser from the filesystem — no server required. Graph data is embedded inline.

**Node attributes:** `id`, `label`, `file`, `lang`, `uploaded_by`, `tags`, `sentiment_label`, `sentiment_score`, `colour`

**Node colours:** green = positive · grey = neutral · red = negative

**Browser controls:** filter by language and uploader via dropdowns; drag nodes; scroll to zoom.

```bash
# Default output: sync/output/graph.json + sync/output/graph.html
python 9-graph/graph.py

# Custom output path
python 9-graph/graph.py --output sync/output/graph.json

# Custom Qdrant host
python 9-graph/graph.py --qdrant-host localhost:6333 --output sync/output/graph.json
```

Then open `sync/output/graph.html` in any browser.

---

## playlist.py

Loads a user profile and returns a ranked JSON playlist from `video_metadata`. No model inference is performed — ranking is computed entirely from tag overlap signals already stored in Qdrant.

### How personalisation works

Personalisation combines two signals:

**1. Role relevance (`role_score`, weight 0.5)**

The user's `role` field is looked up in `roles.yaml` to get a set of relevant tags (e.g. `engineer` → `["maintenance", "equipment", "safety", …]`). Each candidate video's `tags` are compared against that set. A video covering more role-relevant topics scores higher.

```
role_score = |video.tags ∩ role_tags| / |role_tags|
```

**2. Watch history signal (`history_score`, weight 0.4)**

The `watched` list in the profile is cross-referenced against all records in `video_metadata`. The tags from every watched video are collected into a single history tag set. Candidate videos whose tags overlap with that set rank higher — the assumption being that a user who watched several safety videos probably wants more safety content.

```
history_tags  = union of tags across all watched videos
history_score = |video.tags ∩ history_tags| / |history_tags|
```

This means the playlist adapts as `watched` grows: adding a watched video to the profile shifts future recommendations toward related topics without any retraining.

**3. Sentiment bonus (optional, +0.1)**

Passing `--sentiment positive` adds a 0.1 bonus to videos whose `sentiment_label` matches. Useful for onboarding playlists (prefer upbeat content) or risk training (prefer negative to surface known hazard discussions).

**Final score:**
```
score = 0.5 × role_score + 0.4 × history_score + sentiment_bonus
```

### Example

A new hire with role `production_operative` and an empty watch history gets a playlist boosted toward `["production", "safety", "onboarding", …]` tags. After they watch the safety intro, its tags (`["safety", "onboarding"]`) enter the history set — the next playlist run will additionally boost any video tagged `onboarding` or `safety` that they haven't seen yet.

### Usage

```bash
# Personalised playlist, top 10
python 9-graph/playlist.py --user engineer@org.com --top-n 10

# Filter to positive-sentiment videos only
python 9-graph/playlist.py --user engineer@org.com --sentiment positive

# Custom Qdrant host
python 9-graph/playlist.py --user engineer@org.com --qdrant-host localhost:6333
```

### EU AI Act opt-out

Employees can disable personalisation. In opt-out mode the tool returns unranked results (sorted by filename) and does not read or record watch history.

```bash
# Via CLI flag
python 9-graph/playlist.py --user engineer@org.com --no-personalise

# Via profile field — set "personalise": false in profiles/<user>.json
```

---

## profiles/

Each user needs a profile JSON file at `profiles/<user@org.com>.json`. The filename must exactly match the `--user` argument passed to `playlist.py`.

```json
{
  "user": "engineer@org.com",
  "role": "engineer",
  "language": "en",
  "watched": ["safety-intro.mp3"],
  "personalise": true
}
```

| Field | Description |
|---|---|
| `user` | Email address — must match the filename |
| `role` | Must match a key in `roles.yaml` — determines which tags boost the playlist |
| `language` | ISO language code; only videos with a matching `lang` field are returned |
| `watched` | Filenames (basename or full path) to exclude from results and use as history signal |
| `personalise` | `false` permanently opts the user out of personalisation (EU AI Act compliance) |

### How the profile connects to the graph

The `role` → `roles.yaml` → tags chain is the same signal used to colour and filter the knowledge graph. A video's `tags` field (extracted by `analyze.py` and stored in Qdrant) is the shared currency: it drives edge creation in the graph (shared tags = edge), node relevance in the playlist (tag overlap = score boost), and the watch-history signal (watched video tags = future preference).

---

## roles.yaml

Maps role names to relevant tags. The tag list defines what "relevant" means for each role — every video in `video_metadata` whose `tags` overlap with this list gets a score boost for users in that role.

```yaml
engineer:
  - engineering
  - maintenance
  - equipment
  - safety

production_operative:
  - production
  - safety
  - onboarding
```

**Adding a new role:** append a new key with its tag list. The role name must match the `role` field in the corresponding profile files. Tags do not need to be exhaustive — the score is proportional to overlap, so a video tagged `["safety", "cooking"]` still scores for an engineer because of the `safety` match, just not as high as one tagged `["safety", "equipment", "maintenance"]`.

**Tag quality matters:** tags come from `analyze.py`'s Llama 3 extraction. If role-relevant content is not being surfaced, check that the tags extracted for those videos are consistent with the terms listed in `roles.yaml`.

---

## Limitations

### Playlist

**Tag quality is a hard dependency.** Both the role boost and the watch-history signal are computed from the `tags` field extracted by `analyze.py`. If Llama 3 produces inconsistent, generic, or missing tags for a video — or uses different vocabulary from `roles.yaml` (e.g. `"ppe"` vs `"personal-protective-equipment"`) — that video will score near zero regardless of its actual relevance. There is currently no tag normalisation or synonym expansion.

**Watch history is additive but never decays.** Tags accumulate across all watched videos with equal weight. A user who watched 20 safety videos and 1 cooking video will have a history set still dominated by safety tags — but a user who watched the same 20 safety videos two years ago and has since moved into a management role will still be recommended safety content until their profile is manually updated. There is no time-weighting or role-change detection.

**Cold start.** A new user with an empty `watched` list gets a playlist based entirely on role tags. If their role maps to broad tags shared by many videos (e.g. `"safety"` appears on almost everything), the ranking is close to arbitrary within that group. The playlist only meaningfully differentiates once a few videos have been watched.

**Scoring weights are fixed constants.** The `0.5 / 0.4` split between role score and history score is hardcoded. There is no mechanism to tune these per deployment, per role, or based on observed engagement. A production operative with no watch history and an engineer with a long history get ranked by the same formula with the same weights.

**Language filter is exact-match.** `profile.language` is compared directly to `video.lang`. A user with `"language": "en"` will never see `"en-GB"` or `"en-AU"` videos even if the content is fully relevant. Multilingual users (e.g. native Spanish speaker working in an English-language org) must maintain separate profiles or leave `language` blank to see everything unfiltered.

**No deduplication across near-identical videos.** If multiple videos cover the same topic with the same tags, they all score equally and can fill the top-N results. There is no diversity enforcement to ensure the playlist spans different topics.

**Playlist is stateless.** Running `playlist.py` twice with the same profile returns the same results. There is no session state, pagination, or "next batch" mechanism. Updating the `watched` list between runs is a manual operation — there is no API to record a view automatically.

### Knowledge Graph

**Edges are based on tag overlap only.** Two videos are connected if and only if they share at least one tag. Videos that cover the same topic but were tagged differently (synonym problem above) will appear as isolated nodes with no edges, even if semantically they are closely related. A semantic edge (cosine similarity between video embeddings) would surface these relationships but is not implemented — `video_metadata` stores a placeholder vector rather than a real embedding.

**Node sizing is uniform.** All nodes render at the same radius regardless of how frequently a video is watched, how many tags it has, or how central it is in the graph. High-value hub videos are visually indistinct from isolated ones.

**Graph is a static snapshot.** `graph.py` reads Qdrant at the moment it is run and writes a frozen JSON file. The HTML viewer loads that snapshot — it does not poll Qdrant for updates. Re-running `graph.py` and refreshing the browser is required to see newly indexed videos.

**No layout persistence.** The D3.js force simulation runs fresh on every page load. Node positions are not saved, so a manually arranged layout is lost on reload.

---

## Tests

```bash
pytest 9-graph/test_graph.py 9-graph/test_playlist.py -v
```

All tests mock Qdrant — no running services required.
