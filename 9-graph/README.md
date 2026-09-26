# 9-graph — Knowledge Graph & Playlist Generator

Query-layer tools that read from the `video_metadata` Qdrant collection and produce usable outputs with no additional model inference.

**Depends on:** Qdrant (port 6333), populated `video_metadata` collection

---

## Models Used

None — this stage performs no model inference. Graph and playlist outputs are derived entirely from metadata already stored in Qdrant (`tags`, `sentiment_label`, `lang`, etc.) by the upstream pipeline stages.

---

## How it Works

### graph.py

Reads every record from `video_metadata` and produces:

- **`graph.json`** — nodes (one per video) and edges (one per pair of videos that share at least one tag). Edge weight = number of shared tags.
- **`graph.html`** — self-contained D3.js force-directed viewer. Opens directly in a browser — no server required. Graph data is embedded inline.

**Node attributes:** `id`, `label`, `file`, `lang`, `uploaded_by`, `tags`, `sentiment_label`, `sentiment_score`, `colour`

**Node colours:** green = positive · grey = neutral · red = negative

**Browser controls:** filter by language and uploader via dropdowns; drag nodes; scroll to zoom.

### playlist.py

Loads a user profile and returns a ranked JSON playlist. Ranking combines three signals:

**1. Role relevance (`role_score`, weight 0.5)**

The user's `role` is looked up in `roles.yaml` to get a set of relevant tags. Each video's `tags` are compared against that set — more overlap = higher score.

```
role_score = |video.tags ∩ role_tags| / |role_tags|
```

**2. Watch history (`history_score`, weight 0.4)**

Tags from all watched videos are unioned into a history set. Candidate videos whose tags overlap with that set rank higher.

```
history_tags  = union of tags across all watched videos
history_score = |video.tags ∩ history_tags| / |history_tags|
```

**3. Sentiment bonus (optional, +0.1)**

`--sentiment positive` adds a 0.1 bonus to videos whose `sentiment_label` matches.

**Final score:**
```
score = 0.5 × role_score + 0.4 × history_score + sentiment_bonus
```

Tag comparison is **case-insensitive** — `"AI"` and `"ai"` match. Spelling must be exact.

---

## Sample Output

**`sync/output/graph.json`** — graph nodes and edges:

```json
{
  "nodes": [
    {"id": "en/safety-intro", "label": "Safety Introduction", "lang": "en", "tags": ["safety", "onboarding"], "colour": "green"},
    {"id": "en/electrical-basics", "label": "Electrical Basics", "lang": "en", "tags": ["safety", "technical"], "colour": "grey"}
  ],
  "edges": [
    {"source": "en/safety-intro", "target": "en/electrical-basics", "weight": 1}
  ]
}
```

**`sync/output/playlist-engineer@org.com.json`** — ranked playlist:

```json
[
  {"rank": 1, "file": "sync/input/en/safety-intro.mp4", "title": "Safety Introduction", "tags": ["safety", "onboarding"], "sentiment_label": "positive", "score": 0.45},
  {"rank": 2, "file": "sync/input/en/electrical-basics.mp4", "title": "Electrical Basics", "tags": ["safety", "technical"], "sentiment_label": "neutral", "score": 0.30}
]
```

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

## Running locally

```bash
# Default — user engineer@org.com, top 10
bash 9-graph/create-playlist-graph.sh

# Custom user / playlist size
bash 9-graph/create-playlist-graph.sh --user operative@org.com --top-n 5

# Sentiment filter
bash 9-graph/create-playlist-graph.sh --user engineer@org.com --sentiment positive

# EU AI Act opt-out
bash 9-graph/create-playlist-graph.sh --no-personalise --user manager@org.com
```

Or run the scripts directly:

```bash
python 9-graph/graph.py --qdrant-host localhost:6333 --output sync/output/graph.json
python 9-graph/playlist.py --user engineer@org.com --top-n 10
```

---

## Running on LUMI (HPC)

**Prerequisites:** `E-qdrant` service must be running and have written `$SCRATCH/qdrant.endpoint`.

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

Outputs land in `sync/output/`. Logs go to `logs/graph-slurm-<jobid>.out`.

---

## profiles/

Each user needs a profile JSON file at `profiles/<user@org.com>.json`. The filename must exactly match the `--user` argument.

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
| `watched` | Filenames to exclude from results and use as history signal |
| `personalise` | `false` permanently opts the user out of personalisation (EU AI Act compliance) |

---

## roles.yaml

Maps role names to relevant tags. Tags must match the vocabulary extracted by Llama 3 — inspect a few `video_metadata` records to confirm alignment before writing role tags.

**Adding a new role:** append a new key with its tag list. The role name must match the `role` field in profile files.

**If all scores are zero:** the most likely cause is a vocabulary mismatch between `roles.yaml` and the tags stored in Qdrant. Scroll the `video_metadata` collection, inspect the `tags` fields, and update `roles.yaml` to use the same terms.

---

## Limitations

### Playlist

**Tag quality is a hard dependency.** If Llama 3 produces inconsistent or missing tags — or uses different vocabulary from `roles.yaml` — videos will score near zero regardless of their actual relevance. There is no synonym expansion.

**Watch history is additive but never decays.** Tags accumulate with equal weight across all watched videos. There is no time-weighting or role-change detection.

**Cold start.** A new user with no watch history gets a playlist based entirely on role tags. Rankings only meaningfully differentiate once a few videos have been watched.

**Scoring weights are fixed constants.** The `0.5 / 0.4` split is hardcoded with no mechanism to tune per deployment or role.

**Language filter is exact-match.** `profile.language` is compared directly to `video.lang` — `"en"` will not match `"en-GB"`.

**Playlist is stateless.** Updating the `watched` list is a manual operation — there is no API to record a view automatically.

### Knowledge Graph

**Edges are based on tag overlap only.** Videos covering the same topic but tagged differently appear as isolated nodes with no edges.

**Node sizing is uniform.** All nodes render at the same radius regardless of centrality or watch frequency.

**Graph is a static snapshot.** Re-running `graph.py` and refreshing the browser is required to see newly indexed videos.

**No layout persistence.** The D3.js force simulation runs fresh on every page load — manually arranged layouts are lost on reload.

