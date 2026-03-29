# GEMINI.md

# DuckDome project instructions

This repository is a rewrite of DuckDome for a single primary developer.
Favor clean, understandable solutions over clever or over-engineered ones.

## Product shape
DuckDome is:
- an Electron desktop app
- a React frontend
- a Python backend
- a local-first tool for coordinating AI agents

## Repository boundaries
- `apps/web` contains React UI only
- `apps/desktop` contains Electron main/preload only
- `backend` contains Python backend only
- `scripts` contains build/dev orchestration only
- `docs` contains specs and planning docs only

## Working rules
- work on one feature at a time
- do not mix unrelated changes
- do not create duplicate systems
- do not add business logic to bootstrap or launcher files
- do not mark work complete without verification

## Architecture rules
### Frontend
- use feature-oriented organization
- keep UI components focused
- keep business logic out of presentational components

### Electron
- Electron should manage lifecycle, windowing, and backend startup
- do not move core product logic into Electron

### Backend
- keep route handlers thin
- keep business logic in services
- keep persistence in stores
- keep external integrations isolated

## Avoid
- giant files
- giant utility modules
- hidden side effects
- cross-layer leakage
- unnecessary dependencies
- broad refactors during feature tasks

## Scope control
Edit only the files needed for the current task.
If you notice adjacent cleanup, mention it separately instead of doing it automatically.

## Verification
Before concluding that work is done, verify what is relevant:
- lint
- typecheck
- tests
- build
- runtime behavior for the changed feature

If any verification was skipped or could not be run, state that clearly.

## Maintenance bias
Prefer solutions that are:
- obvious
- easy to review
- easy to debug
- easy for one person to keep consistent over time

If unsure, choose the less magical approach.

## Legacy Feature Reference Rule

When implementing any feature, you MUST:

1. Identify the corresponding feature in the legacy repository:
   agentchattr

2. Reference:
   - relevant files
   - relevant behavior
   - expected inputs/outputs

3. Confirm:
   - what behavior must be preserved
   - what is being simplified or changed

4. Explicitly state:
   - "This feature replaces <legacy feature>"
   - "Differences from legacy behavior: ..."

5. Do NOT:
   - re-invent behavior without checking legacy
   - drop functionality without calling it out
   - assume behavior from memory

If unsure, say:
"Legacy behavior unclear — needs confirmation"

The goal is to preserve correctness while improving structure.