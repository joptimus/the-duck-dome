# CLAUDE.md

# DuckDome Claude Guardrails

You are working in a solo-developer repository.

Your primary goal is to produce clean, correct, reviewable changes WITHOUT expanding scope.

---

## Core Rules

### 1. Stay in scope
- Only work on the requested feature
- Do not refactor unrelated code
- Do not “clean things up” outside the task
- If you notice issues, list them separately instead of fixing them

---

### 2. Do not invent architecture
- Follow existing structure
- Do not introduce new patterns or systems
- Do not create alternate implementations of existing functionality

---

### 3. Respect layer boundaries
- Web = UI only
- Desktop = lifecycle only
- Backend = business logic only
- Do not move logic across layers

---

### 4. Keep changes small and reviewable
- Avoid large diffs
- Avoid touching many files
- Avoid mixing feature work with refactors

---

### 5. Do not over-engineer
- Prefer simple solutions
- Do not introduce abstractions unless clearly necessary
- Avoid building systems “for future flexibility”

---

### 6. No hidden behavior
- No magic side effects
- No implicit flows
- No unclear state mutations

---

### 7. Be honest about completion
Do NOT say “done” unless:
- the code builds
- the feature is actually implemented
- obvious edge cases are handled

If something is unverified, say:
- what was not tested
- what may be incomplete

---

### 8. Verification checklist
Before finishing:
- Does the code compile/build?
- Is the feature actually working?
- Did I introduce unrelated changes?
- Did I follow repo structure?

---

### 9. When unsure
Choose the option that is:
1. simpler
2. easier to understand
3. easier for one person to maintain

---

## Final Rule

If you are about to:
- refactor unrelated code
- introduce a new pattern
- expand scope

STOP and do not proceed.

### Legacy Reference Requirement

Before implementing a feature:
- check how it worked in the old repo
- do not guess behavior
- do not silently drop functionality

If behavior is unclear, say so.