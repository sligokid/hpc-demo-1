## Parent PRD

`issues/prd.md`

## What to build

Write `3-sync/setup.md` — a verified, end-to-end onboarding guide covering everything a new developer needs to go from zero to a running sync pipeline on LUMI. Written after the pipeline is working so every command in it is known-good.

The guide covers:
1. GCP project creation and Drive API enablement
2. OAuth2 credentials (Desktop app type) setup in GCP Console
3. `rclone config` walkthrough to generate `rclone.conf` with a `gdrive` remote
4. `chmod 600` and `scp` to LUMI
5. Creating the two Drive folders (`whisper-sync/input`, `whisper-sync/output`)
6. `docker build` and running `test-local.sh` to verify locally
7. SIF conversion (`singularity build`) — including macOS note (requires Linux environment via Lima/Colima)
8. `scp` to upload SIF to LUMI scratch
9. `sbatch 3-sync/hpc/submit-sync.sh` to start the polling chain
10. How to verify the chain is running (`squeue`, `tail logs/`)
11. Cloud provider swap section: GCS — update rclone remote type + two env vars, no script changes; S3 — same pattern

## Acceptance criteria

- [ ] `3-sync/setup.md` exists and covers all 11 sections above
- [ ] A developer following the guide from scratch can reach a running sync job on LUMI without asking for help
- [ ] Every shell command in the guide has been manually verified against the working implementation from issues 001–003
- [ ] The GCS and S3 swap sections include the exact rclone config fields that need changing
- [ ] The macOS SIF conversion note explains the Lima/Colima requirement clearly
- [ ] Token refresh lifetime is documented (active daily use keeps token alive; 6-month inactivity policy noted)

## Blocked by

- Blocked by `issues/003-lumi-deployment-sif-and-slurm-job.md`

## User stories addressed

- User story 10 (rclone config set up once interactively on local machine, copied to HPC)
- User story 15 (GCS/S3 swap documented)
- User story 19 (SLURM script conventions documented)
