# GeminiBridge Integration Plan

> **Date:** 2026-04-04
> **Status:** Design validated, ready for implementation.
> **Scope:** Add a first-class `GeminiBridge` that speaks Gemini CLI's ACP (Agent Client Protocol) over stdio JSON-RPC, mirroring the existing `CodexBridge`. Replaces the legacy one-shot `GeminiExecutor` runner path for bridged agents.

---

## Background

DuckDome already has a unified agent abstraction with two bridge implementations (`backend/src/duckdome/bridges/`):

- `ClaudeBridge` — HTTP hooks + keystroke injection
- `CodexBridge` — stdio JSON-RPC to `codex app-server`

Gemini today is only a one-shot subprocess runner (`backend/src/duckdome/runner/gemini.py::GeminiExecutor`) that runs `gemini --prompt <text>` and returns the final output. It has no streaming, no tool-call visibility, no approval flow, and no session continuity. This makes Gemini a second-class agent in DuckDome.

Gemini CLI ships with **ACP mode** (`gemini --acp`) — a JSON-RPC 2.0 protocol over stdio designed exactly for programmatic control by external tools (IDEs, agent orchestrators). Protocol reference lives in `DevApps/gemini-cli/packages/cli/src/acp/acpClient.ts` and docs in `DevApps/gemini-cli/docs/cli/acp-mode.md`. Gemini uses the open `@agentclientprotocol/sdk` package on the JS side; DuckDome's Python backend will speak the wire protocol directly, same as `codex_bridge.py` does for Codex.

ACP is structurally very similar to Codex's app-server stdio protocol, so the bridge is essentially a reshape of `CodexBridge` with different method names and payload shapes.

---

## ACP Protocol Surface (reference)

**Client → Server methods (used by DuckDome):**

| Method | Purpose |
|---|---|
| `initialize` | Handshake; declare client capabilities (fs proxy support, MCP server info). |
| `authenticate` | Authenticate the user (deferred to env-based auth in v1). |
| `newSession` | Start a new chat session; returns `sessionId`. |
| `loadSession` | Resume an existing session. |
| `prompt` | Send a prompt turn to the agent. |
| `cancel` | Cancel an in-flight turn. |
| `setSessionMode` | Change approval level (e.g. `auto-approve`). |
| `unstable_setSessionModel` | Change model for session. |

**Server → Client notifications (`session/update`):**

| Update type | Meaning |
|---|---|
| `user_message_chunk` | Echo of user prompt (ignored). |
| `agent_message_chunk` | Streaming agent output (delta). |
| `agent_thought_chunk` | Streaming reasoning/thought (delta). |
| `tool_call` | Tool call started; carries `toolCallId`, `tool_name`, `tool_input`. |
| `tool_call_update` | Tool call progress/completion; carries status + optional result. |
| `available_commands_update` | Slash-command list (ignored v1). |

**Server → Client requests:**

| Request | Meaning |
|---|---|
| `requestPermission` | Gemini asks the client to approve a tool call. Reply with `allow_once` / `reject_once`. |
| `fs/readTextFile` | Read a file on behalf of the agent. |
| `fs/writeTextFile` | Write a file on behalf of the agent. |

---

## Architecture

```
┌────────────────────────────────────────────┐
│            DuckDome Backend                 │
│                                             │
│  wrapper/manager.py                         │
│        │                                    │
│        ▼                                    │
│  AgentBridge (abstract)                     │
│    ├─ ClaudeBridge   (HTTP hooks)           │
│    ├─ CodexBridge    (stdio JSON-RPC)       │
│    └─ GeminiBridge   (stdio JSON-RPC / ACP) │  ← new
└────────────────────────────────────────────┘
             │ stdio
             ▼
   gemini --acp   (subprocess, cwd = channel repo)
```

The rest of the backend (channels, chat store, tool approval service, WebSocket broadcasts, frontend) is unchanged — `GeminiBridge` emits the same normalized events as the other bridges, so it plugs into the existing fabric.

---

## Process Startup & Handshake

**Command:**
```
cmd = ["gemini", "--acp"]
cwd = channel.repo_path  (when channel_type == "repo", else None)
env = inherits the parent process env (includes GEMINI_API_KEY / OAuth state)
```

**Handshake sequence on `start(agent_id, config)`:**

1. Spawn `gemini --acp` with `cwd`.
2. Send `initialize` — declare client capabilities:
   - `fs.readTextFile: true`
   - `fs.writeTextFile: true`
   - MCP server info (DuckDome's MCP URL, same one Codex/Claude use) if ACP initialize supports it; otherwise pass via `newSession`.
3. Send `authenticate` only if `initialize` reports unauthenticated. In v1 we do NOT drive interactive auth — if auth fails, the bridge emits `on_error` with a clear "run `gemini auth` in a terminal" message and stays in `offline` state.
4. Send `newSession` — pass repo path and MCP config (if not already passed in `initialize`). Store the returned `sessionId` on the bridge instance.
5. Mark bridge ready; emit `on_status_change(ready)`.

**Open implementation question:** Whether MCP server registration happens in `initialize` or `newSession` must be verified against `acpClient.ts:initialize` and `newSession` handlers before coding.

---

## AgentBridge Method Mapping

| `AgentBridge` method | ACP call | Notes |
|---|---|---|
| `start(agent_id, config)` | spawn + `initialize` (+ `authenticate`?) + `newSession` | Stores `sessionId`; emits `on_status_change(ready)`. |
| `send_prompt(text, channel_id, sender)` | `prompt` with `sessionId` | Fully native; no keystroke injection. Sender/channel context prepended to prompt text using the existing formatting helper. |
| `interrupt()` | `cancel` with `sessionId` | First-class. |
| `approve(approval_id)` | Resolve pending `requestPermission` request with `allow_once` | `approval_id` maps to ACP `toolCallId`. |
| `deny(approval_id, reason)` | Resolve pending `requestPermission` request with `reject_once` | Same correlation. |
| `get_status()` | Internal state machine | Tracked from session updates and turn boundaries. |
| `stop()` | `cancel` if in-flight → close stdio → `proc.terminate()` with grace timeout → `kill()` | Mirrors Codex teardown. |

**Approval correlation:** ACP's `requestPermission` carries a `toolCallId`. We use it as DuckDome's `approval_id` so the existing `ToolApproval` record and frontend flow work without changes.

---

## Event Mapping

All Gemini events are normalized to the existing event dataclasses in `bridges/events.py`, so channels and UI remain backend-agnostic.

| ACP session update | DuckDome event |
|---|---|
| `user_message_chunk` | *(ignored — we already have our own prompt)* |
| `agent_message_chunk` | `AgentMessageDeltaEvent` (streaming); terminal turn also emits `AgentMessageEvent(is_final=True)` |
| `agent_thought_chunk` | `AgentMessageDeltaEvent(kind="thought")` if the event model supports it; otherwise folded into message deltas with a flag |
| `tool_call` | `ToolCallEvent` with `tool_name`, `tool_input`, `call_id = toolCallId` |
| `tool_call_update` (intermediate) | Status update on the existing tool-call record |
| `tool_call_update` (terminal) | `ToolResultEvent` with final result/error |
| `available_commands_update` | *(ignored v1)* |
| incoming `requestPermission` | `ApprovalRequestEvent` + parked `Future`, resolved by `approve()` / `deny()` |
| `prompt` request dispatch | `on_status_change(working)` |
| `prompt` response received | `on_status_change(idle)` |

**Note on turn boundaries:** ACP does not expose explicit `TurnStarted` / `TurnCompleted` notifications like Codex does. We bracket turns on the `prompt` request/response round-trip. Reliability under streaming needs verification during implementation — if gaps are found, fall back to inferring from `tool_call_update` terminal states.

---

## File System Proxy (pass-through)

ACP proxies agent file I/O through the client. During `initialize` we declare `fs.readTextFile: true` and `fs.writeTextFile: true`, and handle the incoming requests directly against the local filesystem scoped to the agent's `cwd`.

```python
async def on_fs_read(params):
    path = _resolve_and_guard(params.path, bridge.cwd)
    return {"content": Path(path).read_text(encoding="utf-8")}

async def on_fs_write(params):
    path = _resolve_and_guard(params.path, bridge.cwd)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(params.content, encoding="utf-8")
    return {}
```

`_resolve_and_guard` rejects paths outside `cwd` (path-traversal defense) with an ACP error. Optional ACP `line` / `limit` params are honored if present. Errors surface as JSON-RPC error responses so Gemini's tool call sees the failure normally.

**Rationale for pass-through (not gated):** Matches Codex/Claude, which hit the disk directly. Approval coverage for fs writes still exists indirectly via `requestPermission` on the tool call that triggered the write. Gating can be added later as a uniform cross-bridge feature if desired.

---

## Wiring

**Manager routing (`wrapper/manager.py`):** Add a third branch behind the existing bridge feature-flag:

```python
if agent_type == "gemini":
    bridge = GeminiBridge(...)
```

A routing test (`TestManagerBridgeRouting.test_use_bridge_gemini_legacy`) already exists for the legacy path — we extend it with a bridge path test and flip the default for `gemini` agents.

**MCP config:** Reuse the existing `wrapper/mcp_config.py::generate_gemini_settings` helper to compute the MCP server URL/config passed during ACP handshake.

**Legacy coexistence:** `runner/gemini.py::GeminiExecutor` and `runner/factory.py` gemini wiring are **kept** during rollout. This matches how CodexBridge coexisted with `CodexExecutor` until live verification (see `docs/plans/2026-04-03-cli-integration-upgrade.md` implementation status). Deletion is a follow-up PR after live verification.

---

## Files Touched

| File | Change |
|---|---|
| `backend/src/duckdome/bridges/gemini_bridge.py` | **New** — `GeminiBridge(AgentBridge)` |
| `backend/src/duckdome/bridges/__init__.py` | Export `GeminiBridge` |
| `backend/src/duckdome/wrapper/manager.py` | Add gemini → bridge routing |
| `backend/src/duckdome/wrapper/mcp_config.py` | Reuse `generate_gemini_settings` for ACP handshake (no behavioral change to the helper itself) |
| `backend/tests/test_bridges.py` | New `TestGeminiBridge*` classes |
| `backend/tests/test_runner_factory.py` | Keep `test_get_gemini_executor` passing (legacy path untouched) |

---

## Tests (TDD)

All tests mock the stdio JSON-RPC transport, same approach as the existing Codex bridge tests.

1. **Handshake** — `initialize` + `newSession` sequence asserts params and stores `sessionId`.
2. **send_prompt** — dispatches ACP `prompt` with the stored `sessionId` and the formatted prompt text.
3. **Message streaming** — `session/update:agent_message_chunk` emits `AgentMessageDeltaEvent`; turn completion emits terminal `AgentMessageEvent`.
4. **Tool call lifecycle** — `session/update:tool_call` emits `ToolCallEvent`; subsequent `tool_call_update` with terminal status emits `ToolResultEvent`.
5. **Approval flow** — incoming `requestPermission` server-request emits `ApprovalRequestEvent` and parks a `Future`; `approve()` resolves with `allow_once`; `deny()` resolves with `reject_once`.
6. **Interrupt** — `interrupt()` sends ACP `cancel` for the current `sessionId`.
7. **Stop** — `stop()` cleans up stdio + process with grace timeout, then kill.
8. **FS proxy read** — `fs/readTextFile` inside `cwd` returns file content; outside `cwd` returns JSON-RPC error.
9. **FS proxy write** — `fs/writeTextFile` inside `cwd` writes and creates parent dirs; outside `cwd` returns error.
10. **Manager routing** — `agent_type="gemini"` with bridge flag routes to `GeminiBridge`, not `GeminiExecutor`.

---

## Out of Scope (with reasons)

| Item | Why excluded | What would bring it in |
|---|---|---|
| Interactive auth flow | Separate subsystem (credential storage, OAuth UI). Gemini CLI already has working env/OAuth auth. Including it doubles the diff and introduces a new security surface. | A decision to own the Gemini auth experience end-to-end in DuckDome. |
| U5 inter-agent routing | Already a tracked phase in the CLI integration plan. Gemini joins routing automatically once U5 lands because it emits the same normalized events. Mixing violates "small, reviewable changes." | U5 being ready to land in the same window. |
| Deleting `runner/gemini.py` | Legacy executor is a safety net if the bridge fails in a live run (matches how Codex rolled out). Premature deletion = no fallback. | Successful live verification of the bridge on a dev machine. |
| Approval gating on fs writes | User chose pass-through fs. Adding gating contradicts that and breaks parity with Codex/Claude. | A cross-bridge decision to gate fs writes uniformly for all backends. |
| Separate UI channel for agent thoughts | Frontend feature, not a transport concern. Violates layer boundaries. For v1, thoughts fold into the delta stream so users still see them. | A unified reasoning-stream feature across all three backends. |

---

## Risks / Items to Verify During Implementation

1. **ACP message shapes.** No Python ACP SDK. We speak wire protocol directly. Each method's exact payload must be verified against `packages/cli/src/acp/acpClient.ts` before coding. `acpClient.ts` is our reference spec.
2. **MCP server registration timing.** Whether MCP info goes in `initialize` capabilities or `newSession` params — verify in the handler code before wiring.
3. **Turn boundaries.** ACP has no explicit `TurnStarted` / `TurnCompleted` notifications. Inferring from `prompt` request/response must be verified reliable under streaming; fall back to terminal `tool_call_update` heuristics if gaps appear.
4. **Auth env inheritance.** Confirm which env vars / credential files `gemini --acp` honors so the spawned subprocess inherits correct auth state.
5. **`requestPermission` schema.** Exact field names (`toolCallId`, decision values `allow_once` / `reject_once`) must be verified against the SDK types before wiring the approval flow.

---

## Phased Rollout

| Phase | What | Status |
|---|---|---|
| G1 | Transport skeleton: spawn, stdio JSON-RPC read/write loop, `initialize` + `newSession` handshake, lifecycle (`start` / `stop`) | Not started |
| G2 | `send_prompt` + `interrupt` + turn boundary tracking | Not started |
| G3 | Event streaming: `agent_message_chunk`, `agent_thought_chunk`, `tool_call`, `tool_call_update` mapped to unified events | Not started |
| G4 | Approval flow: `requestPermission` → `ApprovalRequestEvent` → `approve`/`deny` resolution | Not started |
| G5 | FS proxy: `fs/readTextFile` + `fs/writeTextFile` with cwd guard | Not started |
| G6 | Manager wiring + routing test flip | Not started |
| G7 | Live verification on dev box | Not started |
| G8 | Delete legacy `runner/gemini.py` (follow-up PR) | Not started |

G1–G6 land in the same PR behind the bridge feature flag. G7 is manual verification. G8 is a separate small PR.
