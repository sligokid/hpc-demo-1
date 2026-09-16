## Parent PRD

`prd/task-2-company-brain/prd.md`

## What to build

Two query-layer tools that read from the `video_metadata` Qdrant collection and produce usable outputs without any additional model inference:

1. **`graph.py`** — reads `video_metadata`, exports `graph.json` (nodes = videos, edges = shared tags, node attributes include `sentiment_label`, `lang`, `uploaded_by`, `tags`) and a self-contained `graph.html` D3.js/vis.js viewer that loads `graph.json` statically with no server required. Nodes coloured by sentiment label. Browser-filterable by language and uploader.

2. **`playlist.py`** — loads a user profile from `profiles/<user>.json`, queries `video_metadata` filtered by language, boosts by role-relevant tags from `roles.yaml`, excludes watched videos, ranks by cosine similarity to watch history embeddings, applies configurable sentiment filter, returns top-N as JSON.

Also ships: `roles.yaml` (role → tag mapping) and `profiles/` directory with at least one example profile.

EU AI Act constraint: `playlist.py` must support opt-out (a flag or profile field that disables personalisation and returns unranked results with no watch history recorded).

See PRD: Knowledge Graph, Personalisation Engine sections and Deliverables #8–12.

## Acceptance criteria

- [ ] `python graph.py --output sync/output/graph.json` produces `graph.json` and `graph.html`
- [ ] `graph.html` opens in a browser and renders all indexed videos as nodes with edges between videos that share tags
- [ ] Node colour reflects `sentiment_label` (positive / neutral / negative → distinct colours)
- [ ] Browser filter by `lang` and `uploaded_by` works without a server
- [ ] `python playlist.py --user user@org.com --top-n 10` returns a non-empty ranked JSON playlist for any user with a defined role
- [ ] Already-watched videos (listed in profile `watched` field) are excluded from results
- [ ] `python playlist.py --user user@org.com --no-personalise` returns results without using or recording watch history
- [ ] `roles.yaml` contains mappings for at least the roles mentioned in the PRD (e.g. engineer, production operative)

## Blocked by

- Blocked by `issues/002-embed-server-and-search-local.md` (`video_metadata` collection must be populated)

## User stories addressed

- The knowledge graph shows that the line-jam video is closely related to three others on equipment maintenance — surfacing a practical onboarding path no one explicitly curated (PRD Goal 2).
- A new hire's playlist is pre-populated with safety and operational content matched to their role, ordered by relevance and filtered to exclude already-watched content (PRD Goal 4).
- Employees can opt out of personalisation and browse all content freely without any record being kept (EU AI Act compliance).
