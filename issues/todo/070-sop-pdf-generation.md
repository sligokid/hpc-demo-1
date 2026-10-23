## Parent PRD

`prd/11-sop/prd.md`

## What to build

Extend `11-sop/sop.py` to convert the generated `.sop.md` to a PDF using `weasyprint`. The conversion pipeline is: Markdown → HTML (via the `markdown` Python library) → PDF (via `weasyprint`), with a CSS stylesheet at `11-sop/sop_style.css` embedded in the HTML for print-ready A4 formatting.

Both `.sop.md` and `.sop.pdf` are written on every successful generation run.

## Acceptance criteria

- [ ] `11-sop/sop_style.css` exists with A4 `@page` margins, a clean sans-serif font stack, heading styles, and bordered tables
- [ ] `sop.py` writes `{stem}.sop.pdf` alongside `{stem}.sop.md` on every successful run
- [ ] The PDF is generated via `markdown` library → HTML → `weasyprint` render
- [ ] The stylesheet is embedded in the HTML at render time
- [ ] `test_sop.py` asserts a non-empty `.sop.pdf` file is created after a mocked Ollama call
- [ ] The skip-if-done check (from issue 069) treats the pair as done only when both `.sop.md` and `.sop.pdf` exist
- [ ] `requirements.txt` (or equivalent) in `11-sop/` includes `weasyprint` and `markdown`

## Blocked by

- Blocked by `issues/todo/069-sop-core-markdown-generation.md`

## User stories addressed

- User story 4
- User story 5
