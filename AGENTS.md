# AGENTS.md

# DuckDome agent instructions

You are working in the DuckDome rewrite repository.

Your job is to produce clean, reviewable code for a single-developer project.
Optimize for clarity, maintainability, and correctness.
Do not optimize for cleverness.

## What DuckDome is
DuckDome is a local-first Electron app with a React frontend and a Python backend.
The product helps a single developer coordinate AI agents safely and reliably.

## Repo shape
- `apps/web` = React UI only
- `apps/desktop` = Electron only
- `backend` = Python backend only
- `scripts` = dev/build scripts only
- `docs` = planning and architecture docs only

## Non-negotiable rules
1. One feature at a time.
2. Do not make unrelated edits.
3. Do not create alternate architectures or duplicate systems.
4. Do not add business logic to the wrong layer.
5. Do not claim a task is complete unless it was verified.

## Layer boundaries
### Web
- Put UI code in `apps/web`
- Organize by feature, not by dumping everything into shared folders
- Keep components presentational when possible
- Put feature logic in hooks, feature services, or state modules

### Desktop
- Put Electron main and preload code in `apps/desktop`
- Electron is responsible for app lifecycle and backend startup only
- Do not put product business logic in Electron

### Backend
- Put backend code in `backend`
- Routes call services
- Services contain business logic
- Stores handle persistence
- Integrations talk to external systems
- Do not put real logic in bootstrap files like `main.py` or app factory files

## Forbidden patterns
- giant catch-all files
- giant `utils` files
- global mutable state shared across unrelated modules
- duplicate entrypoints
- mixing refactors with feature work
- adding new dependencies without a clear reason
- touching generated files unless required

## File discipline
Only edit files needed for the current task.
If you find a structural issue outside the task, note it, but do not silently expand scope.

## Verification requirements
Before saying work is done, verify what applies:
- lint passes
- typecheck passes
- tests pass
- app builds
- changed behavior is exercised
- no obvious console/runtime errors introduced

If you could not verify something, say exactly what was not verified.

## Code style expectations
- prefer simple, explicit code
- prefer small focused modules
- avoid hidden side effects
- prefer composition over sprawling inheritance or indirection
- avoid premature abstractions
- do not introduce patterns that require a big mental model for a solo maintainer

## Git and review expectations
- work on one feature branch
- keep commits scoped and readable
- keep diffs reviewable
- expect CodeRabbit to review your work
- fix structural review comments, not just style comments

## Decision rule
When multiple solutions are possible, choose the one that:
1. is easiest for a solo developer to maintain
2. preserves clean layer boundaries
3. reduces setup and runtime complexity
4. avoids magic behavior

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