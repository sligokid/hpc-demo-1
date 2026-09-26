## Parent PRD

`prd/task-2-company-brain/prd.md`

## What to build

Write `5-embed/README.md` covering setup and usage for all three environments (local, Docker, HPC) and documenting the EU AI Act compliance constraints that are design requirements for this system.

This is a HITL issue: the compliance language must be reviewed and approved by a human before merging. The PRD notes that CSC's Senior Coordinator for Trustworthy AI has assessed SLICK+ as not high-risk — the README must accurately reflect the constraints that follow from that assessment.

See PRD: Governance & EU AI Act Compliance section and Deliverable #22.

## Acceptance criteria

- [ ] `5-embed/README.md` covers local startup sequence (Qdrant, embed-server, pipeline)
- [ ] `5-embed/README.md` covers Docker startup sequence
- [ ] `5-embed/README.md` covers HPC startup sequence (SIF build, sbatch order)
- [ ] README documents all five EU AI Act constraints verbatim from the PRD:
  - No individual performance scoring visible to managers
  - Opt-out required — employees can disable personalisation with no record kept
  - No management-visible engagement data in standard mode
  - Consent-based data collection — DPA required before processing real employee data on LUMI-G
  - Training data for this PRD uses public FLEURS and synthetic/dummy inputs only
- [ ] README explains how `playlist.py --no-personalise` satisfies the opt-out requirement
- [ ] **Human review gate:** compliance section signed off before merge

## Blocked by

- Blocked by `issues/006-hpc-slurm-deployment.md` (all three environments must work before they can be documented accurately)

## User stories addressed

- Any team member can set up the full stack in any environment by following the README alone.
- Compliance constraints are documented at the code level, not just in the PRD, making them auditable.
