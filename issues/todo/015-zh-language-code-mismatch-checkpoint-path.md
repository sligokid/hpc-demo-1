## Parent PRD

`prd/task-2-company-brain/prd.md`

## Problem

Training and inference disagree on the Mandarin language code, and the pipeline is configured with the code that training does **not** produce.

| Component | Code | Source |
|---|---|---|
| `LANGUAGE_CODES` key | `zh-CN` | `1-train/train.py:29` |
| Training array | `zh-CN` | `1-train/hpc/train-sbatch-gpu.sh:34` — `LANGUAGES=("en" "es" "fr" "zh-CN" "ar")` |
| Checkpoint on disk | `zh-CN` | `ls checkpoints/` → `ar en es fr zh-CN` |
| Pipeline config | **`zh`** | `pipeline.yaml:12` — `languages: [en, es, fr, zh, ar]` |
| Checkpoint path the pipeline looks for | **`checkpoints/zh`** | `pipeline.py:205` — `model_dir = checkpoints / lang` |

So for any Mandarin file, `pipeline.py:206-209` hits:

```python
if not model_dir.is_dir():
    print(f"  SKIP — no checkpoint at {model_dir}")
```

Mandarin transcription silently never runs, even though a perfectly good `checkpoints/zh-CN` exists on disk. The file is counted as an error, no `.done` sidecar is written, and — like the other stuck files — it would be resubmitted every 10 minutes. Until PR #9, a language table in the root `README.md` papered over the discrepancy by listing the locale `cmn_hans_cn` alongside a `checkpoints/zh` path, which matched neither the training output nor the pipeline config.

This directly undermines two PRD success criteria: cross-language retrieval (English query returning the correct non-English video) cannot pass for Mandarin if Mandarin content is never indexed.

**PR #9 note:** the root `README.md` previously contained a language table whose Checkpoint Path column read `checkpoints/zh` — matching neither the training output nor `pipeline.yaml`, and papering over the discrepancy. PR #9 **deleted that table entirely**, which removes one wrong statement but also removes the only place the five language codes were documented together. The `## Pipeline Overview` diagram at `README.md:13` still says `zh-CN`. When this issue lands, the language table should be restored with the canonical code, not left deleted.

This is a live bug affecting a fifth of the supported languages, not merely a documentation nit — but it is currently invisible because no Mandarin file has been uploaded to `sync/input/zh/`.

## What to build

Make the language codes consistent across training, the pipeline config, and the documentation, so Mandarin transcription actually runs.

Decide on one canonical code and apply it everywhere. `zh-CN` is the FLEURS/HF-aligned form already used by training and present on disk; `zh` is the ISO 639-1 form used by the pipeline config. Either works, but one must win.

Recommended: keep `zh-CN` as canonical, since that is what `checkpoints/` already contains — changing it means retraining or renaming, whereas changing `pipeline.yaml` is a one-line edit. Note this requires the `sync/input/` directory to be named `zh-CN` rather than `zh`, because `pipeline.py:165` infers the language from the parent directory name when `--file` is used, and the HPC array task relies on that.

- Update `pipeline.yaml:12` to the canonical code.
- Ensure the input directory naming convention matches — `sync/input/<lang>/` must use the same code the config lists, or `--file` runs will infer the wrong language. Consider normalising the inferred value in `pipeline.py` rather than depending on directory naming.
- Restore the five-language table to the root `README.md`, deleted in PR #9, with a Checkpoint Path column that matches reality. Include the FLEURS locale (`en_us`, `es_419`, `fr_fr`, `cmn_hans_cn`, `ar_eg`) that the deleted table carried — that information is now only in `1-train/train.py` and is worth keeping visible.
- Check `1-train/README.md` and the `LANGUAGES` arrays in both `train-sbatch-gpu.sh` and `train-sbatch-cpu.sh` for consistency.
- Add a startup check that warns when a language in `pipeline.yaml` has no matching checkpoint directory, so this class of mismatch is caught immediately rather than per-file.

## Acceptance criteria

- [ ] A single canonical Mandarin code is used in `pipeline.yaml`, `1-train/train.py`, and both training submit scripts
- [ ] `checkpoints/<canonical-code>` is the path the pipeline resolves for Mandarin
- [ ] A Mandarin file in `sync/input/` transcribes, analyses, embeds, and indexes successfully
- [ ] `pipeline.py` no longer prints `SKIP — no checkpoint` for Mandarin
- [ ] The root `README.md` has a five-language table restored, with a Checkpoint Path column that matches the directories on disk
- [ ] The FLEURS locale for each language is documented in that table
- [ ] Language codes are consistent across `README.md`, `pipeline.yaml`, `1-train/README.md`, and the submit scripts
- [ ] A check warns at startup if any configured language lacks a checkpoint directory
- [ ] The other four languages (`en`, `es`, `fr`, `ar`) continue to work unchanged

## Blocked by

- None - can start immediately

## Related

- `issues/009-readme-intro-orientation-block.md` — the new intro block must state whichever Mandarin code this issue settles on.

## User stories addressed

- Mandarin content is transcribed and indexed, as required by the five-language scope and the cross-language retrieval success criterion (target > 0.70).
- The language code is unambiguous across code, config, and documentation, and the five supported languages are documented in one place.
