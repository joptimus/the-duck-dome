# DuckDome Migration Handoff

> **Last updated:** 2026-03-29
> **Purpose:** Everything a fresh Claude Code session needs to continue the migration work.

---

## Current State

### What Exists
- **PR #8** (`feature/runner-visibility`) — OPEN, CodeRabbit review fixes pushed, awaiting re-review
  - Wires frontend to real backend `/api/messages` endpoint
  - Adds Claude runner visibility (working/failure notices in chat)
  - Adds markdown rendering for assistant messages
  - All 7 CodeRabbit comments addressed in commit `ab1f184`

### What's Been Produced
- `docs/migration/migration-plan.md` — Full feature-by-feature comparison of agentchattr vs DuckDome
- `docs/migration/pr-plan.md` — 12 ordered PRs with scope, changes, dependencies, verification
- `docs/migration/handoff.md` — This file

### Repository Layout
```text
the-duck-dome/
├── apps/web/          → React frontend (Vite, JSX, plain CSS)
├── apps/desktop/      → Electron shell
├── backend/           → Python FastAPI (models → stores → services → routes)
│   └── src/duckdome/
│       ├── models/    → message.py, channel.py, trigger.py, run.py
│       ├── stores/    → message_store.py, channel_store.py, trigger_store.py
│       ├── services/  → message_service.py, channel_service.py, trigger_service.py, runner_service.py
│       ├── routes/    → messages.py, channels.py, triggers.py, deliveries.py, runners.py, health.py
│       └── runner/    → claude.py, context.py
├── docs/              → Plans, investigations, migration docs
└── scripts/           → dev.sh
```

### Key Files to Read First
- `AGENTS.md` — Non-negotiable coding rules for all agents
- `CLAUDE.md` — Claude-specific guardrails
- `docs/migration/pr-plan.md` — The PR sequence to execute

---

## PR Execution Sequence

### Phase A: Sequential Blockers (must be done in order)

```text
PR #8  → Merge when CodeRabbit approves (check: gh pr view 8)
PR #9  → Message type field (chat | system)
PR #10 → WebSocket backend endpoint
```

### Phase B: Parallel Tracks (after PR #10 merges)

These are independent and can be assigned to separate agents in worktrees:

| Track | PR | Branch Name | What It Does |
|-------|-----|-------------|-------------|
| Frontend | #11 | `feature/websocket-frontend` | WebSocket client, remove polling |
| Safety | #12 | `feature/loop-guard` | Per-channel hop counter, system messages |
| MCP-1 | #13 | `feature/mcp-chat-tools` | MCP bridge with chat_send + chat_read |
| Runner | #16 | `feature/runner-expansion` | Pluggable executor factory |
| Rules | #17 | `feature/rules-system` | Rules model + store + service |

### Phase C: Dependent on Phase B completions

| PR | Branch Name | Depends On | What It Does |
|----|-------------|-----------|-------------|
| #14 | `feature/mcp-identity` | #13 | chat_join + agent identity |
| #15 | `feature/mcp-transport` | #14 | HTTP transport on port 8200 |
| #18 | `feature/rules-api` | #17 + #13 | Rules REST routes + MCP tool |
| #19 | `feature/tool-approvals` | #10 | Tool approval system |
| #20 | `feature/jobs-system` | #10 | Jobs/tasks system |

---

## How to Launch Parallel Agents

After PR #10 is merged into main, use this pattern:

```
You: "Start PR #11, #12, #13, #16, and #17 in parallel using isolated worktrees"
```

Claude Code will use the Agent tool with `isolation: "worktree"` for each, giving each agent its own branch and copy of the repo. Each agent should:

1. Read `AGENTS.md` and `CLAUDE.md`
2. Read `docs/migration/pr-plan.md` for their specific PR scope
3. Create branch, implement, test, commit
4. Push and create PR via `gh pr create`

---

## How to Execute a Specific PR

Give Claude Code a prompt like:

```
Implement PR #12 (loop guard) from docs/migration/pr-plan.md.
- Read the PR plan for exact scope and changes
- Read AGENTS.md for coding rules
- Reference agentchattr/apps/server/src/router.py for legacy behavior
- Create branch feature/loop-guard
- Follow TDD: write tests first, then implement
- Run pytest to verify
- Push and create PR
```

---

## Commands Cheat Sheet

```bash
# Check PR #8 status
gh pr view 8 --json state,reviewDecision

# Merge PR #8 when approved
gh pr merge 8 --merge

# Run backend tests
cd backend && .venv/bin/python -m pytest tests/ -v

# Build frontend
cd apps/web && npx vite build

# Start dev environment
./scripts/dev.sh

# Check what's on main
git log --oneline origin/main | head -10
```

---

## Guardrails Reminder

From AGENTS.md and CLAUDE.md — these are non-negotiable:

1. **One feature at a time** — each PR is one capability
2. **Layer boundaries** — routes → services → stores, no shortcuts
3. **Legacy reference rule** — check agentchattr behavior before implementing
4. **No scope creep** — if you find issues outside the PR, note them, don't fix them
5. **Verify before claiming done** — tests pass, build passes, behavior exercised
6. **Small reviewable diffs** — CodeRabbit will review every PR

---

## Legacy Reference Paths

When implementing features, reference these agentchattr files:

| Feature | Legacy File | Path |
|---------|------------|------|
| Loop guard | router.py | `agentchattr/apps/server/src/router.py` |
| Rules | rules.py | `agentchattr/apps/server/src/rules.py` |
| Jobs | jobs.py | `agentchattr/apps/server/src/jobs.py` |
| MCP bridge | mcp_bridge.py | `agentchattr/apps/server/src/mcp_bridge.py` |
| Tool approvals | tool_approvals.py | `agentchattr/apps/server/src/tool_approvals.py` |
| Sessions | session_engine.py | `agentchattr/apps/server/src/session_engine.py` |
| WebSocket | app.py | `agentchattr/apps/server/src/app.py` (lines 95-280) |
| Agent wrappers | wrapper.py | `agentchattr/apps/server/src/wrapper.py` |
| Chat UI | components/chat/ | `agentchattr/apps/web/src/components/chat/` |
| Zustand stores | stores/ | `agentchattr/apps/web/src/stores/` |

---

## Immediate Next Action

1. Check if PR #8 has been approved: `gh pr view 8 --json reviewDecision`
2. If approved → merge it: `gh pr merge 8 --merge`
3. Start PR #9 (message type field) — smallest PR, <1 day
4. Then PR #10 (WebSocket backend) — unlocks parallel work
5. Then launch parallel agents for Phase B
