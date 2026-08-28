# 002 — Stdin support

## Parent PRD

`prd/4.metadata/prd.md`

## What to build

Extend `analyze.py` so that passing `-` as the value of `--transcript` reads the transcript from `sys.stdin` instead of a file. This enables shell pipelines such as `python infer.py ... | python analyze.py --transcript -` without an intermediate file.

## Acceptance criteria

- [ ] `python analyze.py --transcript -` reads transcript text from stdin
- [ ] `echo "some transcript" | python analyze.py --transcript -` produces valid JSON output
- [ ] `python infer.py ... | python analyze.py --transcript -` works end-to-end in a single pipeline
- [ ] All other behaviour (model flag, output format, exit codes) is unchanged when using stdin

## Blocked by

- `issues/001-core-script-happy-path.md`

## User stories addressed

- User story 2: pipe output of `infer.py` into `analyze.py` without a temporary file
- User story 11: read transcript from stdin using `-` as the file path
