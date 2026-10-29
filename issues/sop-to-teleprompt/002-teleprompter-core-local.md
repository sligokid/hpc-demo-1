## Parent PRD

`issues/prd-sop-to-teleprompter.md`

## What to build

Build `11-sop/teleprompter.py` — the core SOP-to-teleprompter-script converter — and its local runner. The script reads a written SOP from `inbox/{lang}/`, calls Ollama for a structured JSON response, renders it into a teleprompter Markdown script following the client's template and formatting rules, and writes an SME review checklist alongside it.

Covers all functional requirements from the PRD: input format handling, LLM JSON-then-render approach, teleprompter formatting rules, runtime estimate calculation, review checklist, and idempotency guard.

## Acceptance criteria

- [ ] `11-sop/teleprompter.py` accepts `--sop`, `--output`, `--ollama-host`, `--model` CLI args
- [ ] Input formats supported: `.sop.md`, `.md`, `.txt`, `.pdf`, `.docx`
- [ ] Output `{stem}.teleprompter.md` contains all four sections: Hook, Walkthrough, Pitfalls (if applicable), Outro
- [ ] Metadata block includes auto-calculated runtime estimate (`~X min Y sec` at 140 wpm)
- [ ] `[Presenter Name]` placeholder present in Hook section
- [ ] Teleprompter Audio blocks contain no bullet points or bold text
- [ ] Numbers written out in full (`one thousand`, not `1,000`); acronyms hyphenated (`S-O-P`)
- [ ] `{stem}.teleprompter.review.md` checklist written alongside the script
- [ ] Re-running on already-processed files is a no-op (idempotency)
- [ ] `11-sop/local/run-teleprompter.sh` runs the script end-to-end locally
- [ ] `11-sop/test_teleprompter.py` passes with mocked Ollama (no live service required)

## Blocked by

- `issues/001-shared-ollama-utility.md`

## User stories addressed

- Core conversion: SOP → teleprompter video script (Functional Requirements, Technical Design sections of PRD)
- SME review step built into the flow (Goals section of PRD)
- Stage 1: Local delivery (Delivery Stages section of PRD)
