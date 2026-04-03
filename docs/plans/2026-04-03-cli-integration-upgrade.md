# CLI Integration Upgrade Plan

> **Date:** 2026-04-03
> **Status:** Research complete for both Claude Code CLI and Codex CLI.
> **Scope:** Replace platform-specific interception with native CLI integrations. Build a unified agent abstraction so Claude Code and Codex agents can work together in the same channel as a team.

---

## Background

DuckDome currently intercepts agent activity through three heavyweight, platform-specific mechanisms:

1. **MCP Proxy** (`wrapper/mcp_proxy.py`) — Local HTTP proxy sitting between each agent and the real MCP server. Intercepts JSON-RPC `tools/call` requests, extracts tool names/args, gates execution via approval service.
2. **Console Monitor** (`wrapper/console_monitor.py`) — Windows-only thread that polls the agent's console buffer every 1s via subprocess, pattern-matches permission prompts, injects approve/deny keystrokes.
3. **Keystroke Injection** (`injector_windows.py` / tmux `send-keys`) — Sends keystrokes to agent console for task injection and approval responses.

### Problems with current approach

- **Windows-only** for console monitor and keystroke injection
- **Fragile** — console buffer scraping breaks when CLI output format changes
- **No tool response data** — MCP proxy sees requests but not all response details
- **No subagent visibility** — relies on MCP proxy per-agent, misses internal agent lifecycle
- **Heavy** — requires running a full HTTP proxy per agent process
- **Race conditions** — polling-based with fingerprint dedup to avoid duplicates

---

## Research Findings

### Source: Claude Code CLI (`yasasbanukaofficial/claude-code`)

The CLI has a mature hook system with 26 event types. Hooks can be `command` (shell), `prompt` (LLM), `agent` (agentic verifier), or **`http`** (POST to URL). The `http` type is the key integration point for DuckDome.

### Source: AgentPeek (`TranHuuHoang/agentpeek`)

Uses `command` hooks that append to a JSONL file. Simpler but passive — cannot approve/block/modify. DuckDome needs the bidirectional capability of HTTP hooks.

---

## Available Hook Events (Claude Code CLI)

Every hook receives a base payload:
```json
{
  "session_id": "string",
  "transcript_path": "string",
  "cwd": "string",
  "agent_id": "string (optional, present in subagents)",
  "agent_type": "string (optional)",
  "permission_mode": "string (optional)"
}
```

### Tool Lifecycle

| Event | Additional Fields | Can Respond |
|---|---|---|
| `PreToolUse` | `tool_name`, `tool_input`, `tool_use_id` | `decision: approve/block`, `updatedInput`, `additionalContext`, `permissionDecision` |
| `PostToolUse` | `tool_name`, `tool_input`, `tool_response`, `tool_use_id` | `continue`, `suppressOutput` |
| `PostToolUseFailure` | `tool_name`, `tool_input`, `tool_use_id`, `error`, `is_interrupt` | `continue` |
| `PermissionRequest` | `tool_name`, `tool_input`, `permission_suggestions[]` | `decision: approve/block` |
| `PermissionDenied` | `tool_name`, `tool_input`, `tool_use_id`, `reason` | observe only |

### Agent Lifecycle

| Event | Additional Fields | Can Respond |
|---|---|---|
| `SubagentStart` | `agent_id`, `agent_type` | `additionalContext` |
| `SubagentStop` | `agent_id`, `agent_type`, `agent_transcript_path`, `last_assistant_message` | observe only |
| `Stop` | `stop_hook_active`, `last_assistant_message` | observe only |
| `StopFailure` | `error`, `error_details`, `last_assistant_message` | observe only |

### Session Lifecycle

| Event | Additional Fields |
|---|---|
| `SessionStart` | `source: startup/resume/clear/compact`, `model` |
| `SessionEnd` | `reason` |
| `Notification` | `message`, `title`, `notification_type` |

### Task Lifecycle

| Event | Additional Fields |
|---|---|
| `TaskCreated` | `task_id`, `task_subject`, `task_description` |
| `TaskCompleted` | `task_id`, `task_subject`, `task_description` |

### Other Events

| Event | Additional Fields |
|---|---|
| `PreCompact` | `trigger: manual/auto`, `custom_instructions` |
| `PostCompact` | `trigger`, `compact_summary` |
| `FileChanged` | `file_path`, `event: change/add/unlink` |
| `CwdChanged` | `old_cwd`, `new_cwd` |
| `ConfigChange` | `source`, `file_path` |
| `InstructionsLoaded` | `file_path`, `memory_type`, `load_reason` |
| `WorktreeCreate` | `name` |
| `WorktreeRemove` | `worktree_path` |
| `Elicitation` | `mcp_server_name`, `message`, `mode`, `requested_schema` |
| `ElicitationResult` | `mcp_server_name`, `action`, `content` |
| `TeammateIdle` | `teammate_name`, `team_name` |
| `UserPromptSubmit` | `prompt` |

### Hook Response Capabilities

Sync hook responses can include:
```json
{
  "continue": true,
  "decision": "approve | block",
  "reason": "explanation",
  "systemMessage": "warning shown to user",
  "stopReason": "message when continue=false",
  "suppressOutput": false,
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "auto-approved by DuckDome",
    "updatedInput": { "command": "modified-command" },
    "additionalContext": "injected into conversation"
  }
}
```

### Subagent Transcript Files

Each subagent writes JSONL at:
```
~/.claude/projects/<project-hash>/<session-id>/subagents/agent-<agent-id>.jsonl
```

With metadata sidecar:
```
agent-<agent-id>.meta.json  →  { agentType, worktreePath?, description? }
```

---

## Migration Plan

### Phase 1: HTTP Hook Receiver (new component)

**Goal:** Add an HTTP endpoint to DuckDome backend that receives hook payloads from the CLI.

**New file:** `backend/src/duckdome/hooks/receiver.py`

- FastAPI router mounted at `/hooks/claude` (or similar)
- Accepts POST with the hook JSON payload
- Routes events by `hook_event_name` to appropriate handlers
- Returns appropriate hook response JSON for gating events

**Changes to agent startup (`wrapper/manager.py`):**
- When spawning a Claude Code agent, write a temporary `settings.local.json` or use `--settings` flag that configures HTTP hooks pointing at the DuckDome hook receiver
- All relevant events route to `http://localhost:{port}/hooks/claude`

### Phase 2: Replace Console Monitor with Hook-Based Approval

**Goal:** Remove Windows console buffer scraping for permission prompts.

**Replace:**
- `console_monitor.py` permission prompt detection
- `console_reader.py` subprocess calls
- Pattern matching via `match_permission_prompt()`

**With:**
- `PermissionRequest` HTTP hook → creates ToolApproval record, broadcasts to frontend
- `PreToolUse` HTTP hook → checks pending approvals, returns `{ decision: "approve/block" }`
- `PermissionDenied` HTTP hook → logs denied actions

**Key behavior change:**
- Current: Poll console → detect prompt → create approval → user responds → inject keystroke
- New: CLI fires hook → DuckDome creates approval → user responds → DuckDome returns response in next hook call

**Note:** The `PreToolUse` hook fires BEFORE the permission prompt, so DuckDome can approve/block at the hook level, preventing the permission prompt from ever appearing. This is cleaner than responding to prompts after they show.

### Phase 3: Replace MCP Proxy Tool Interception with Hooks

**Goal:** Remove the per-agent HTTP proxy for tool call visibility.

**Replace:**
- `mcp_proxy.py` HTTP interception of `tools/call` JSON-RPC
- `_extract_tool_calls()` parsing
- `_requires_approval()` checking
- `_request_tool_approval()` gating

**With:**
- `PreToolUse` HTTP hook → full tool_name + tool_input, can approve/block/modify
- `PostToolUse` HTTP hook → full tool_name + tool_input + tool_response
- `PostToolUseFailure` HTTP hook → error tracking

**What MCP proxy does that hooks also do:**
- See every tool call name and arguments ✓
- Gate tool execution (approve/deny) ✓
- Rewrite tool arguments (via `updatedInput`) ✓
- Track which channel/context the agent is in (via `agent_id`) ✓

**What MCP proxy does that hooks do NOT do:**
- Inject `sender`/`agent_type` into MCP tool arguments at the transport level
- The workaround: use `additionalContext` in `PreToolUse` response to inject context, or handle identity injection in the MCP server itself

### Phase 4: Enhanced Agent Lifecycle Tracking

**Goal:** Get richer agent state data than currently available.

**New data from hooks:**
- `SubagentStart` → know immediately when a subagent spawns, with type
- `SubagentStop` → get `last_assistant_message` and `agent_transcript_path` for result extraction
- `Stop` / `StopFailure` → know when agent finishes, with error details
- `TaskCreated` / `TaskCompleted` → track internal task progress
- `PostCompact` → get `compact_summary` to know what the agent "remembers"

**New data from transcript files:**
- Tail `agent-<id>.jsonl` for real-time message streaming (richer than hook events)
- Read `agent-<id>.meta.json` for agent metadata

### Phase 5: Settings Injection for Agent Startup

**Goal:** Automatically configure hooks when DuckDome spawns agents.

**Approach:**
- Generate a per-agent `settings.local.json` in a temp directory
- Include all HTTP hook configurations pointing at DuckDome's receiver
- Set `CLAUDE_CONFIG_DIR` or use CLI flags to point at the config
- Include the `async: true` flag for observation-only hooks (PostToolUse, SubagentStop, etc.)
- Use sync (blocking) hooks only for gating events (PreToolUse, PermissionRequest)

**Hook configuration template:**
```json
{
  "hooks": {
    "PreToolUse": [{
      "hooks": [{ "type": "http", "url": "http://127.0.0.1:{{port}}/hooks/claude?agent={{agent_id}}" }]
    }],
    "PostToolUse": [{
      "hooks": [{ "type": "http", "url": "http://127.0.0.1:{{port}}/hooks/claude?agent={{agent_id}}", "async": true }]
    }],
    "PostToolUseFailure": [{
      "hooks": [{ "type": "http", "url": "http://127.0.0.1:{{port}}/hooks/claude?agent={{agent_id}}", "async": true }]
    }],
    "SubagentStart": [{
      "hooks": [{ "type": "http", "url": "http://127.0.0.1:{{port}}/hooks/claude?agent={{agent_id}}", "async": true }]
    }],
    "SubagentStop": [{
      "hooks": [{ "type": "http", "url": "http://127.0.0.1:{{port}}/hooks/claude?agent={{agent_id}}", "async": true }]
    }],
    "Stop": [{
      "hooks": [{ "type": "http", "url": "http://127.0.0.1:{{port}}/hooks/claude?agent={{agent_id}}", "async": true }]
    }],
    "PermissionRequest": [{
      "hooks": [{ "type": "http", "url": "http://127.0.0.1:{{port}}/hooks/claude?agent={{agent_id}}" }]
    }],
    "Notification": [{
      "hooks": [{ "type": "http", "url": "http://127.0.0.1:{{port}}/hooks/claude?agent={{agent_id}}", "async": true }]
    }],
    "TaskCreated": [{
      "hooks": [{ "type": "http", "url": "http://127.0.0.1:{{port}}/hooks/claude?agent={{agent_id}}", "async": true }]
    }],
    "TaskCompleted": [{
      "hooks": [{ "type": "http", "url": "http://127.0.0.1:{{port}}/hooks/claude?agent={{agent_id}}", "async": true }]
    }]
  }
}
```

---

## What Stays the Same

| Component | Reason |
|---|---|
| **Queue system** (`queue.py`) | No CLI equivalent for injecting new prompts into a running session |
| **Keystroke injection** (for new tasks) | Still needed to send prompts to agent stdin |
| **WebSocket broadcast** | Frontend communication layer is independent of interception method |
| **Tool approval service** | Business logic stays; only the trigger mechanism changes |
| **Message store** | JSONL chat storage is DuckDome's own layer |

---

## Component Removal After Migration

| Component | Remove after |
|---|---|
| `console_monitor.py` | Phase 2 |
| `console_reader.py` | Phase 2 |
| `injector_windows.py` (approval injection only) | Phase 2 |
| `mcp_proxy.py` (tool interception) | Phase 3 |
| `match_permission_prompt()` | Phase 2 |

**Note:** `injector_windows.py` is still needed for queue-based task injection (sending new prompts). Only the approval-response injection path is removed.

---

## Risks and Open Questions

1. **Hook timeout** — HTTP hooks default to 10 minutes, but blocking `PreToolUse` hooks hold up the agent. DuckDome's approval flow needs to respond within a reasonable time or the hook times out.

2. **Settings injection** — Need to verify that `settings.local.json` in the agent's working directory is picked up, or find the right env var / CLI flag to point at custom settings.

3. **Async hook delivery order** — Async hooks fire in the background. Events may arrive out of order at the receiver. Need to handle this in the receiver (use `tool_use_id` for correlation).

4. **Subagent hooks** — Hooks fire from subagents too (with `agent_id` populated). Need to verify that a parent session's hook config propagates to subagents automatically.

5. **MCP tool argument rewriting** — The MCP proxy currently rewrites tool arguments to inject `sender`/`agent_type`. The `updatedInput` hook response field can partially replace this, but only for tool input — not for adding fields the MCP server expects. May need to handle identity at the MCP server level instead.

6. **Codex CLI** — Codex may have different or no hook system. Analysis pending. The plan should be modular enough to support multiple CLI backends.

---

## Appendix: Codex CLI Integration

> **Source:** `yasasbanukaofficial/codex` (Rust core at `codex-rs/`)
> **Status:** Analysis complete

### Architecture Overview

Codex is fundamentally different from Claude Code. It's a Rust application with:

- **codex-rs/core** — Agent loop, tool execution
- **codex-rs/protocol** — Event/submission queue protocol (SQ/EQ pattern)
- **codex-rs/hooks** — Hook engine (reads `hooks.json` files)
- **codex-rs/app-server** — JSON-RPC server with **stdio** and **WebSocket** transports
- **codex-rs/app-server-protocol** — Full typed protocol (requests, responses, notifications)
- **sdk/python** — Python SDK with generated Pydantic models

### Key Difference: App-Server Protocol

Codex has a **first-class app-server** that external clients can connect to via WebSocket (`ws://IP:PORT`) or stdio. This is dramatically richer than Claude Code's hook system — it's a full bidirectional protocol, not just event callbacks.

The app-server exposes:

**Client Requests (things DuckDome can ask Codex to do):**
| Request | Wire Name | Purpose |
|---|---|---|
| `ThreadStart` | `thread/start` | Start a new conversation thread |
| `ThreadResume` | `thread/resume` | Resume an existing thread |
| `ThreadFork` | `thread/fork` | Fork a thread (like subagent) |
| `ThreadList` | `thread/list` | List all threads |
| `ThreadRead` | `thread/read` | Read thread contents |
| `ThreadArchive` | `thread/archive` | Archive a thread |
| `ThreadRollback` | `thread/rollback` | Rollback conversation |
| `ThreadCompactStart` | `thread/compact/start` | Trigger compaction |
| `TurnStart` | `turn/start` | Submit a new turn (prompt) |
| `TurnSteer` | `turn/steer` | Steer the agent mid-turn |
| `TurnInterrupt` | `turn/interrupt` | Interrupt current turn |
| `ThreadShellCommand` | `thread/shellCommand` | Run a shell command |
| `ModelList` | `model/list` | List available models |
| `SkillsList` | `skills/list` | List available skills |

**Server Notifications (events DuckDome receives):**
| Notification | Wire Name | Data |
|---|---|---|
| `TurnStarted` | `turn/started` | Turn ID, thread ID |
| `TurnCompleted` | `turn/completed` | Turn result, items |
| `AgentMessageDelta` | `item/agentMessage/delta` | Streaming text chunks |
| `ItemStarted` | `item/started` | Tool call / action begin |
| `ItemCompleted` | `item/completed` | Tool call / action end with result |
| `ExecCommandBegin` | — | Shell command about to execute |
| `ExecCommandOutputDelta` | — | Incremental command output |
| `ExecCommandEnd` | — | Command finished |
| `McpToolCallBegin` | — | MCP tool call starting |
| `McpToolCallEnd` | — | MCP tool call finished |
| `HookStarted` | `hook/started` | Hook execution began |
| `HookCompleted` | `hook/completed` | Hook execution finished |
| `ThreadTokenUsageUpdated` | `thread/tokenUsage/updated` | Token counts |
| `ThreadNameUpdated` | `thread/name/updated` | Thread name change |
| `ContextCompacted` | `thread/compacted` | Compaction happened |
| `PatchApplyBegin` / `End` | — | Code patch being applied |
| `TurnDiffUpdated` | `turn/diff/updated` | File changes in this turn |
| `CollabAgentSpawnBegin` | — | Multi-agent spawn started |
| `CollabAgentSpawnEnd` | — | Multi-agent spawn finished |

**Server Requests (things Codex asks DuckDome to decide):**
| Request | Wire Name | Purpose |
|---|---|---|
| `CommandExecutionRequestApproval` | `item/commandExecution/requestApproval` | Approve/deny a shell command |
| `ApplyPatchRequestApproval` | `item/applyPatch/requestApproval` | Approve/deny a code patch |
| `RequestPermissions` | — | Request permission changes |
| `RequestUserInput` | — | Request user input |
| `McpServerElicitationRequest` | — | MCP server needs user decision |

### Codex Hook System (Limited)

Codex has a hook system but it's much simpler than Claude Code's:

**Events:** Only 5 — `PreToolUse`, `PostToolUse`, `SessionStart`, `UserPromptSubmit`, `Stop`

**Hook types:** Only `command` (shell). No `http` hooks. `prompt` and `agent` types exist in the schema but are stubs.

**Config file:** `hooks.json` (not `settings.json`)

**Platform:** **Not supported on Windows** — the engine returns early with a warning on Windows.

**Format:**
```json
{
  "hooks": {
    "PreToolUse": [{ "matcher": "Bash", "hooks": [{ "type": "command", "command": "..." }] }],
    "PostToolUse": [{ "hooks": [{ "type": "command", "command": "..." }] }],
    "Stop": [{ "hooks": [{ "type": "command", "command": "..." }] }]
  }
}
```

### Recommendation: Use App-Server Protocol, Not Hooks

For Codex, the **app-server WebSocket protocol** is the right integration point, not hooks. It's:

1. **Bidirectional** — DuckDome can send commands AND receive events
2. **Full fidelity** — 40+ notification types vs 5 hook events
3. **Approval built-in** — Server requests for approval are first-class
4. **Streaming** — Agent message deltas, command output deltas
5. **Thread management** — Start, stop, fork, resume, list, read threads programmatically
6. **Cross-platform** — WebSocket works on Windows (hooks don't)

### Codex Integration Plan

#### Phase C1: WebSocket Client

**Goal:** Connect DuckDome to Codex's app-server via WebSocket.

**Approach:**
- Spawn `codex-app-server --listen ws://127.0.0.1:{port}` instead of raw `codex` CLI
- Connect a WebSocket client from DuckDome backend to the app-server
- Parse JSON-RPC notifications into DuckDome's internal event model

#### Phase C2: Thread Management

**Goal:** Use Codex's native thread API instead of queue/keystroke injection.

**Replace queue system for Codex agents with:**
- `thread/start` to create new conversations
- `turn/start` to submit prompts (replaces keystroke injection entirely)
- `turn/interrupt` to stop a running turn
- `thread/read` to get conversation history

**This eliminates the need for:**
- Queue files for Codex agents
- Keystroke injection for Codex agents
- Console monitoring for Codex agents

#### Phase C3: Approval via Server Requests

**Goal:** Handle Codex's approval flow natively.

**How it works:**
1. Codex sends `CommandExecutionRequestApproval` server request
2. DuckDome creates a ToolApproval record, broadcasts to frontend
3. User approves/denies in UI
4. DuckDome responds to the JSON-RPC request with the decision

This is cleaner than either console scraping or HTTP hooks because the approval protocol is a first-class JSON-RPC request/response — no polling, no timeouts.

#### Phase C4: Rich Event Streaming

**Goal:** Surface Codex's detailed events in DuckDome's UI.

**Map Codex notifications to DuckDome events:**
- `item/agentMessage/delta` → real-time agent output streaming
- `item/started` / `item/completed` → tool call tracking
- `turn/diff/updated` → file change tracking
- `thread/tokenUsage/updated` → usage monitoring
- `CollabAgentSpawnBegin/End` → multi-agent visibility

---

---

## Unified Multi-Agent Architecture

DuckDome is a multi-agent workspace where Claude Code and Codex agents operate in the same channels, communicate with each other, and collaborate on tasks as a team. The integration layer must abstract away CLI differences so the rest of DuckDome (channels, chat, UI, task routing) doesn't care which CLI backend an agent runs on.

### Design Principle

```
┌─────────────────────────────────────────────────────┐
│                   DuckDome Backend                   │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ Channels │  │  Chat /  │  │   Task Router /   │  │
│  │          │  │ Messages │  │  Inter-Agent Msgs  │  │
│  └────┬─────┘  └────┬─────┘  └────────┬──────────┘  │
│       │              │                 │              │
│       └──────────────┼─────────────────┘              │
│                      │                                │
│              ┌───────▼────────┐                       │
│              │  AgentBridge   │  ← unified interface  │
│              │  (abstract)    │                        │
│              └───┬────────┬──┘                        │
│                  │        │                            │
│       ┌──────────▼──┐  ┌─▼───────────┐               │
│       │ ClaudeBridge│  │ CodexBridge │               │
│       │ (HTTP hooks)│  │ (WebSocket) │               │
│       └──────┬──────┘  └──────┬──────┘               │
└──────────────┼────────────────┼───────────────────────┘
               │                │
        ┌──────▼──────┐  ┌─────▼──────┐
        │ Claude Code │  │   Codex    │
        │   CLI       │  │ App-Server │
        └─────────────┘  └────────────┘
```

### AgentBridge Interface

A common interface that both CLI backends implement:

```python
class AgentBridge(ABC):
    """Unified interface for controlling an agent regardless of CLI backend."""

    @abstractmethod
    async def start(self, agent_id: str, config: AgentConfig) -> None:
        """Spawn the agent process and establish connection."""

    @abstractmethod
    async def send_prompt(self, text: str, channel_id: str, sender: str) -> None:
        """Send a message/task to the agent."""

    @abstractmethod
    async def interrupt(self) -> None:
        """Interrupt the agent's current turn."""

    @abstractmethod
    async def approve(self, approval_id: str) -> None:
        """Approve a pending tool/command execution."""

    @abstractmethod
    async def deny(self, approval_id: str, reason: str) -> None:
        """Deny a pending tool/command execution."""

    @abstractmethod
    async def get_status(self) -> AgentStatus:
        """Get current agent status (working/idle/offline)."""

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully stop the agent."""

    # Events — the bridge emits these to the DuckDome event bus
    on_tool_call: Callable[[ToolCallEvent], None]
    on_tool_result: Callable[[ToolResultEvent], None]
    on_message: Callable[[AgentMessageEvent], None]
    on_message_delta: Callable[[AgentMessageDeltaEvent], None]
    on_approval_request: Callable[[ApprovalRequestEvent], None]
    on_status_change: Callable[[StatusChangeEvent], None]
    on_subagent_start: Callable[[SubagentEvent], None]
    on_subagent_stop: Callable[[SubagentEvent], None]
    on_error: Callable[[ErrorEvent], None]
```

### ClaudeBridge Implementation

Uses HTTP hooks + keystroke injection:

- **`send_prompt()`** → keystroke injection (still needed — no native prompt API)
- **`approve()`/`deny()`** → respond to `PreToolUse` / `PermissionRequest` HTTP hook
- **Events** → received via HTTP hook POST endpoint
- **`start()`** → spawn `claude` process with injected `settings.local.json` containing HTTP hook config
- **`interrupt()`** → send Ctrl+C keystroke or `Escape` to agent console

### CodexBridge Implementation

Uses app-server WebSocket protocol:

- **`send_prompt()`** → `turn/start` JSON-RPC request (fully native, no keystroke injection)
- **`approve()`/`deny()`** → respond to `CommandExecutionRequestApproval` JSON-RPC server request
- **Events** → received via WebSocket notifications
- **`start()`** → spawn `codex-app-server --listen ws://127.0.0.1:{port}`, connect WebSocket
- **`interrupt()`** → `turn/interrupt` JSON-RPC request

### Unified Event Model

Both bridges emit normalized events into the same DuckDome event bus:

```python
@dataclass
class ToolCallEvent:
    agent_id: str
    agent_type: str          # "claude" or "codex"
    channel_id: str
    tool_name: str
    tool_input: dict
    call_id: str
    timestamp: float

@dataclass
class AgentMessageEvent:
    agent_id: str
    agent_type: str
    channel_id: str
    text: str
    is_final: bool           # False for deltas, True for complete
    timestamp: float

@dataclass
class ApprovalRequestEvent:
    agent_id: str
    agent_type: str
    channel_id: str
    approval_id: str
    tool_name: str
    tool_input: dict
    description: str         # Human-readable description
    timestamp: float
```

### Inter-Agent Communication

When agents are in the same channel, they need to see each other's output and be able to hand off tasks. The flow:

```
1. User sends "Build the API and write tests for it" to #backend channel
2. Task Router assigns "Build the API" to codex-agent-1
3. Task Router assigns "Write tests" to claude-agent-1 (waiting on codex)

4. DuckDome sends prompt to codex-agent-1 via CodexBridge.send_prompt()
5. CodexBridge receives item/completed notifications → emits ToolCallEvent, AgentMessageEvent
6. DuckDome broadcasts these to channel #backend (visible in UI)

7. When codex-agent-1 finishes (TurnCompleted), DuckDome:
   a. Captures the result via on_message callback
   b. Builds a context prompt for claude-agent-1:
      "codex-agent-1 completed: [result summary]. Now write tests for it."
   c. Sends via ClaudeBridge.send_prompt()

8. claude-agent-1 works, emits events via HTTP hooks
9. DuckDome broadcasts to channel #backend
```

**Key design decisions for inter-agent communication:**

1. **Agents don't talk directly** — DuckDome mediates all communication. This keeps the system observable and controllable.

2. **Context injection** — When routing a task that depends on another agent's output, DuckDome injects the relevant context into the prompt. The agent doesn't need to know it's collaborating.

3. **Channel-scoped visibility** — All agents in a channel see each other's messages in the chat UI. Humans can intervene, redirect, or add context at any point.

4. **Approval delegation** — If a Claude agent needs approval and a Codex agent could provide context, DuckDome can surface it in the approval UI. But agents don't auto-approve each other.

### MCP Server Role in Inter-Agent Communication

The existing MCP server (`chat_send`, `chat_read`, `chat_join`) remains the agent-facing interface for communication. Both CLI types connect to the same MCP server. What changes is how DuckDome *observes* that communication:

- **Today:** MCP proxy intercepts `tools/call` JSON-RPC at the HTTP level
- **Claude Code future:** `PostToolUse` HTTP hook sees MCP tool calls with `tool_name` and `tool_response`
- **Codex future:** `McpToolCallBegin`/`McpToolCallEnd` notifications from WebSocket

The MCP server itself doesn't change — it's already agent-agnostic. Only the observation/interception layer changes.

### Phased Rollout

| Phase | What | Enables |
|---|---|---|
| **U1: AgentBridge interface** | Define abstract interface + event model | Clean separation before any refactor |
| **U2: CodexBridge** | Implement WebSocket-based bridge for Codex | Codex agents with full native control |
| **U3: ClaudeBridge** | Implement HTTP-hook-based bridge for Claude Code | Claude agents without console scraping |
| **U4: Manager refactor** | Refactor `wrapper/manager.py` to use bridges | Both agent types through unified path |
| **U5: Inter-agent routing** | Task handoff, context injection, dependency tracking | Agents collaborating in channels |
| **U6: Legacy removal** | Remove console monitor, MCP proxy, keystroke injection (for Codex) | Clean codebase |

**U2 before U3** because Codex's WebSocket protocol is a cleaner integration — build the pattern right with Codex first, then adapt for Claude Code's more constrained hook system.

---

## Summary: Claude Code vs Codex Integration

| Aspect | Claude Code | Codex |
|---|---|---|
| **Best integration point** | HTTP hooks (`settings.json`) | App-server WebSocket protocol |
| **How to observe** | Hook events (26 types) | Server notifications (40+ types) |
| **How to approve** | `PreToolUse` hook response | JSON-RPC server request/response |
| **How to send prompts** | Keystroke injection (still needed) | `turn/start` request (native) |
| **How to manage sessions** | External (queue files) | `thread/*` requests (native) |
| **Streaming** | Not via hooks (need transcript tail) | `agentMessage/delta`, `commandExecution/outputDelta` |
| **Windows support** | HTTP hooks work | App-server works (hooks don't) |
| **Complexity** | Medium (HTTP receiver + settings injection) | Low (WebSocket client) |

Codex's app-server is the more complete integration — it gives DuckDome full programmatic control over the agent without any of the current workarounds (queue files, keystroke injection, console scraping, MCP proxy). Claude Code's HTTP hooks are a good improvement over the status quo but still require keystroke injection for prompt submission.
