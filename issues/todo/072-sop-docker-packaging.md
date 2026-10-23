## Parent PRD

`prd/11-sop/prd.md`

## What to build

Package the SOP stage for Docker. The Dockerfile installs `weasyprint` and its system-level dependencies (`libpango-1.0-0`, `libcairo2`, `libgdk-pixbuf2.0-0`, `libffi-dev`, and a font package) so that PDF generation works inside the container without host system deps. Provide `build.sh` and `run.sh` scripts following the pattern in `10-agent/docker/`.

## Acceptance criteria

- [ ] `11-sop/docker/Dockerfile` exists and installs all weasyprint system dependencies via `apt-get`
- [ ] `11-sop/docker/Dockerfile` installs Python deps: `weasyprint`, `markdown`, `requests`, `pyyaml`
- [ ] `11-sop/docker/build.sh` builds the image with a consistent tag (e.g. `slick-sop:latest`)
- [ ] `11-sop/docker/run.sh` runs `sop.py` for a single file, binding the project root as `/workspace`
- [ ] `docker build` completes without errors
- [ ] Running `docker run ... sop.py --transcript <file> --analysis <file>` against a fixture transcript produces `.sop.md` and `.sop.pdf` (requires a running Ollama instance on the host; document in README)
- [ ] `11-sop/docker/README.md` documents build and run commands, and notes that Ollama must be reachable via `--ollama-host host.docker.internal:11434` on Mac/Linux

## Blocked by

- Blocked by `issues/todo/071-sop-pipeline-integration.md`

## User stories addressed

- User story 15
- User story 18
