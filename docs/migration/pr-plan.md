# DuckDome PR Plan

> **Date:** 2026-03-29
> **Baseline:** After PR #8 merges (runner visibility + frontend wired to /api/messages)
> **Ordering agreed with:** Claude + ChatGPT consensus

---

## PR #9: Add `type` field to Message model

### Goal
Add minimal message type discrimination (`chat` | `system`) to prevent schema retrofit later. Every feature after this (loop guard, sessions, rules) needs typed messages.

### Scope
- `backend/src/duckdome/models/message.py` — add `type` field with StrEnum
- `backend/src/duckdome/services/message_service.py` — default to `chat`, allow `system` on send
- `backend/src/duckdome/stores/message_store.py` — no changes needed (JSONL serializes new field automatically)
- `backend/tests/` — update model tests, add type-aware tests
- `apps/web/src/features/channel-shell/ChannelShell.jsx` — pass `type` through normalizeMessages

### Changes
```python
# models/message.py
class MessageType(StrEnum):
    CHAT = "chat"
    SYSTEM = "system"

class Message(BaseModel):
    # ... existing fields ...
    type: MessageType = MessageType.CHAT
```

- `MessageService.send()` accepts optional `type` parameter (defaults to `chat`)
- `normalizeMessages()` in frontend preserves `message.type` field
- Existing stored messages without `type` default to `chat` on deserialization (Pydantic default handles this)

### Depends On
PR #8 merged

### Verification
- `pytest` passes
- Send a message via API: `POST /api/messages` with `{"text": "hello", "channel": "...", "sender": "human"}` — response includes `"type": "chat"`
- Send with explicit type: `{"text": "loop guard triggered", ..., "type": "system"}` — response includes `"type": "system"`
- Old messages without `type` field load correctly (default to `chat`)

---

## PR #10: WebSocket backend endpoint

### Goal
Add a WebSocket endpoint that broadcasts real-time events. This replaces the 3-second polling loop in the frontend.

### Scope
- `backend/src/duckdome/ws/` — new module
  - `manager.py` — ConnectionManager (track connected clients, broadcast)
  - `events.py` — event type definitions
- `backend/src/duckdome/routes/websocket.py` — WS /ws endpoint
- `backend/src/duckdome/app.py` — wire WebSocket route + pass manager to services
- `backend/src/duckdome/services/message_service.py` — emit event on message send
- `backend/src/duckdome/services/trigger_service.py` — emit event on trigger state change
- `backend/tests/test_websocket.py` — connection + broadcast tests

### Changes

**ConnectionManager:**
```python
class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket): ...
    def disconnect(self, ws: WebSocket): ...
    async def broadcast(self, event: dict): ...
```

**Event types (start minimal, grow later):**
```python
# Outbound events
"new_message"          # { type, message }
"trigger_state_change" # { type, trigger_id, state }
"agent_status_change"  # { type, agent_id, status }
```

**WebSocket route:**
```python
@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

**Service integration:**
- `MessageService.send()` calls `manager.broadcast({"type": "new_message", "message": msg.model_dump()})`
- `TriggerService.complete_trigger()` / `fail_trigger()` / `claim_trigger()` broadcast state changes
- `TriggerService.heartbeat()` broadcasts agent status changes

### Depends On
PR #9

### Verification
- Connect via `wscat -c ws://localhost:8000/ws`
- Send a message via REST `POST /api/messages` — WebSocket client receives `new_message` event
- Claim/complete a trigger — WebSocket client receives `trigger_state_change`
- Agent heartbeat — WebSocket client receives `agent_status_change`
- Multiple clients receive the same broadcast
- Disconnecting one client doesn't break others

---

## PR #11: WebSocket frontend client + remove polling

### Goal
Wire the frontend to WebSocket for real-time updates. Remove the 3-second polling interval.

### Scope
- `apps/web/src/api/ws.js` — new WebSocket client with reconnection
- `apps/web/src/features/channel-shell/ChannelShell.jsx` — replace polling with WebSocket events
- `apps/web/src/features/channel-shell/channelShell.css` — connection status indicator (optional)

### Changes

**WebSocket client (`ws.js`):**
```javascript
export function createWsClient(url, onEvent) {
  let ws = null;
  let reconnectTimer = null;

  function connect() {
    ws = new WebSocket(url);
    ws.onmessage = (e) => onEvent(JSON.parse(e.data));
    ws.onclose = () => { reconnectTimer = setTimeout(connect, 2000); };
  }

  connect();
  return { close: () => { ws?.close(); clearTimeout(reconnectTimer); } };
}
```

**ChannelShell changes:**
- Remove `refreshTick` state and 3-second `setInterval`
- Add `useEffect` that creates WebSocket connection on mount
- On `new_message` event: append to messagesByChannelId if channel matches
- On `trigger_state_change` event: update trigger in state
- On `agent_status_change` event: update agent in state
- Keep initial REST fetch on channel switch (load history), but stop polling after that
- Add small connection indicator (connected/reconnecting) in UI

### Depends On
PR #10

### Verification
- Open app in browser
- Send message via API — appears in chat immediately without refresh
- Agent heartbeat changes — runtime strip updates live
- Trigger claimed/completed — trigger summary updates live
- Kill backend, restart — frontend reconnects automatically
- Switch channels — loads history via REST, then receives live updates

---

## PR #12: Loop guard

### Goal
Prevent infinite agent-to-agent @mention loops. When agent A mentions agent B who mentions agent A, the system must detect the cycle and stop routing after a configurable max hop count.

### Scope
- `backend/src/duckdome/services/message_service.py` — add loop guard state machine
- `backend/src/duckdome/services/trigger_service.py` — no changes (triggers still fire; guard prevents new triggers)
- `backend/tests/test_loop_guard.py` — dedicated test file

### Changes

**Loop guard state (per channel, in memory):**
```python
class LoopGuard:
    def __init__(self, max_hops: int = 4):
        self._hops: dict[str, int] = {}   # channel_id → hop count
        self._paused: dict[str, bool] = {} # channel_id → paused
        self.max_hops = max_hops

    def check(self, channel_id: str, sender: str, known_agents: list[str]) -> bool:
        """Returns True if routing should proceed, False if guard triggered."""
        ...

    def reset(self, channel_id: str) -> None:
        """Human message resets the guard."""
        ...
```

**Integration in MessageService.send():**
- If sender is a known agent: increment hop count for channel
- If hop count > max_hops: skip trigger creation, post system message ("Loop guard: {max_hops} agent-to-agent hops reached"), set paused=True
- If sender is human (not in known_agents): reset hop count and paused state
- If paused and sender is agent: skip trigger creation silently

**System message on guard trigger:**
- Uses `type: "system"` from PR #9
- Text: "Loop guard activated — {n} consecutive agent-to-agent hops in #{channel}. Human message required to resume."
- Broadcast via WebSocket from PR #10

### Depends On
PR #9 (message type), PR #10 (WebSocket broadcast)

### Verification
- Send `@claude do something` — Claude responds, mentions `@codex`, Codex responds, mentions `@claude`... after 4 hops, system message appears
- Human sends any message — guard resets, agents can route again
- Guard is per-channel — triggering guard in channel A doesn't affect channel B
- `pytest` passes with dedicated loop guard tests

---

## PR #13: MCP bridge — chat_send + chat_read tools

### Goal
Expose the two most critical MCP tools so agents can send and read messages. This is the minimum for agent connectivity.

### Scope
- `backend/src/duckdome/mcp/` — new module
  - `bridge.py` — FastMCP server with tool definitions
  - `cursor_store.py` — per-agent, per-channel read cursors
- `backend/tests/test_mcp_bridge.py` — tool invocation tests
- `backend/pyproject.toml` — add `mcp` dependency

### Changes

**MCP tools:**
```python
@mcp.tool()
def chat_send(text: str, channel: str) -> str:
    """Send a message to a channel."""
    # Calls MessageService.send() with sender=agent_identity
    ...

@mcp.tool()
def chat_read(channel: str, limit: int = 20) -> str:
    """Read recent messages from a channel. Returns messages since last read cursor."""
    # Uses cursor_store to track per-agent read position
    # Advances cursor after read
    # Calls MessageService.process_agent_read() to mark deliveries
    ...
```

**Cursor store:**
```python
class CursorStore:
    """Tracks per-agent, per-channel read position. Persists to cursors.json."""
    def get_cursor(self, agent: str, channel: str) -> str | None: ...
    def set_cursor(self, agent: str, channel: str, msg_id: str) -> None: ...
```

**Agent identity:**
- For this PR, agent identity comes from a required `agent_name` parameter on each tool call
- PR #14 adds proper session-based identity

### Depends On
PR #10 (WebSocket — messages sent via MCP should broadcast)

### Verification
- Start MCP server on port 8200
- Call `chat_send` tool with text="hello from claude" — message appears in channel
- Call `chat_read` tool — returns recent messages
- Call `chat_read` again — returns only new messages (cursor advanced)
- Messages sent via MCP trigger WebSocket broadcast to frontend
- `pytest` passes

---

## PR #14: MCP bridge — chat_join + agent identity

### Goal
Add agent registration via MCP and proper identity handling so agents authenticate themselves when connecting.

### Scope
- `backend/src/duckdome/mcp/bridge.py` — add chat_join tool, add identity context
- `backend/src/duckdome/mcp/identity.py` — agent identity extraction from MCP session
- `backend/tests/test_mcp_identity.py` — identity + join tests

### Changes

**New MCP tool:**
```python
@mcp.tool()
def chat_join(channel: str, agent_type: str) -> str:
    """Register agent in a channel. Must be called before chat_send/chat_read."""
    # Calls TriggerService.register_agent()
    # Sets agent identity for this MCP session
    ...
```

**Identity flow:**
- `chat_join` establishes identity for the MCP session
- Subsequent `chat_send` / `chat_read` calls use the established identity (no more `agent_name` parameter)
- If `chat_send` / `chat_read` called before `chat_join`: return error "Agent not registered"

**Legacy reference:** `mcp_bridge.py:chat_claim` — same concept, simplified

### Depends On
PR #13

### Verification
- Call `chat_join` with agent_type="claude" — agent appears in channel agent list
- Call `chat_send` — sender is "claude" (from identity, not parameter)
- Call `chat_send` without prior `chat_join` — error returned
- Agent shows as "idle" in runtime strip after join
- `pytest` passes

---

## PR #15: MCP HTTP transport

### Goal
Serve the MCP bridge over HTTP so external agents (Claude Code, Codex, Gemini) can connect.

### Scope
- `backend/src/duckdome/mcp/transport.py` — HTTP transport setup on configurable port
- `backend/src/duckdome/main.py` — start MCP server alongside FastAPI
- Config: port 8200 (default), configurable via env var `DUCKDOME_MCP_PORT`

### Changes

**Transport setup:**
- Use `mcp` library's streamable-http transport
- Bind to `127.0.0.1:8200`
- Start in background thread/task alongside main FastAPI server

**Startup flow:**
```
main.py starts:
  1. FastAPI on :8000 (REST + WebSocket)
  2. MCP on :8200 (HTTP transport)
```

**Agent config snippet (for Claude Code `~/.claude.json`):**
```json
{
  "mcpServers": {
    "duckdome": {
      "url": "http://localhost:8200/mcp"
    }
  }
}
```

### Depends On
PR #14

### Verification
- Start DuckDome — both ports listen (8000 + 8200)
- Configure Claude Code to use MCP server at localhost:8200
- Claude Code can call `chat_join`, `chat_send`, `chat_read` via MCP
- Messages from Claude appear in DuckDome frontend in real-time
- `pytest` passes

---

## PR #16: Runner expansion — pluggable executors

### Goal
Refactor the runner module to support multiple agent types beyond Claude CLI.

### Scope
- `backend/src/duckdome/runner/base.py` — abstract executor interface
- `backend/src/duckdome/runner/claude.py` — refactor to implement interface
- `backend/src/duckdome/runner/codex.py` — Codex CLI executor
- `backend/src/duckdome/runner/gemini.py` — Gemini CLI executor
- `backend/src/duckdome/runner/factory.py` — executor factory (agent_type → executor)
- `backend/src/duckdome/services/runner_service.py` — use factory instead of hardcoded Claude
- `backend/tests/test_runner_factory.py` — factory selection tests

### Changes

**Executor interface:**
```python
class BaseExecutor(ABC):
    @abstractmethod
    def execute(self, ctx: RunContext, timeout_s: int = 120) -> RunResult: ...
```

**Factory:**
```python
def get_executor(agent_type: str) -> BaseExecutor:
    match agent_type:
        case "claude": return ClaudeExecutor()
        case "codex": return CodexExecutor()
        case "gemini": return GeminiExecutor()
        case _: raise ValueError(f"Unknown agent type: {agent_type}")
```

**RunnerService changes:**
- Replace `claude_execute(ctx)` with `get_executor(trigger.target_agent_type).execute(ctx)`

### Depends On
PR #10 (WebSocket for broadcasting run results)

### Verification
- `POST /api/runners/execute` with a Claude trigger — works as before
- Factory returns correct executor for each agent type
- Unknown agent type raises clear error
- `pytest` passes

---

## PR #17: Rules system — model + store + service

### Goal
Add the rules system backend (shared working style rules that agents follow).

### Scope
- `backend/src/duckdome/models/rule.py` — Rule model with status (draft/active/archive)
- `backend/src/duckdome/stores/rule_store.py` — JSONL persistence with epoch versioning
- `backend/src/duckdome/services/rule_service.py` — propose, activate, deactivate, list
- `backend/tests/test_rules.py` — full test coverage

### Changes

**Rule model:**
```python
class RuleStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVE = "archive"

class Rule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str = Field(max_length=160)
    status: RuleStatus = RuleStatus.DRAFT
    author: str | None = None
    reason: str | None = Field(default=None, max_length=240)
    created_at: float = Field(default_factory=time.time)
```

**RuleStore:** JSONL with epoch counter (integer that increments on any mutation). Agents can check freshness via epoch comparison.

**RuleService:** propose(text, author) → draft rule, activate(id), deactivate(id), list_active(), get_epoch()

**Legacy ref:** `rules.py` — same concept, simplified (no reorder, no max-10 limit)

### Depends On
PR #9 (message types — rule proposals could use system messages)

### Verification
- Create rule via service — persists to JSONL
- Activate rule — status changes, epoch increments
- List active rules — only active ones returned
- Check epoch — matches mutation count
- `pytest` passes

---

## PR #18: Rules API routes + MCP tool

### Goal
Expose rules via REST API and add `chat_rules` MCP tool so agents can read rules.

### Scope
- `backend/src/duckdome/routes/rules.py` — REST endpoints
- `backend/src/duckdome/mcp/bridge.py` — add `chat_rules` tool
- `backend/src/duckdome/app.py` — wire rules routes
- `backend/tests/test_rules_routes.py` — API tests

### Changes

**Routes:**
```
GET    /api/rules                → list all rules
GET    /api/rules/active         → list active rules only
GET    /api/rules/freshness      → return current epoch
POST   /api/rules                → propose new rule (status: draft)
PATCH  /api/rules/{id}           → edit rule text
POST   /api/rules/{id}/activate  → activate rule
POST   /api/rules/{id}/archive   → archive rule
```

**MCP tool:**
```python
@mcp.tool()
def chat_rules() -> str:
    """List active rules. Agents should check and follow these."""
    ...
```

### Depends On
PR #17, PR #13 (MCP bridge exists)

### Verification
- `POST /api/rules` creates draft rule
- `POST /api/rules/{id}/activate` activates it
- `GET /api/rules/active` returns only active rules
- `chat_rules` MCP tool returns active rules
- WebSocket broadcasts rule changes
- `pytest` passes

---

## PR #19: Tool approvals — model + store + service + routes

### Goal
Add the tool approval system so humans can control which tools agents use.

### Scope
- `backend/src/duckdome/models/tool_approval.py` — ToolApproval model
- `backend/src/duckdome/stores/tool_approval_store.py` — JSONL persistence
- `backend/src/duckdome/services/tool_approval_service.py` — request, approve, deny, set_policy
- `backend/src/duckdome/routes/tool_approvals.py` — REST endpoints
- `backend/src/duckdome/app.py` — wire routes
- `backend/tests/test_tool_approvals.py` — tests

### Changes

**Model:**
```python
class ToolApproval(BaseModel):
    id: str
    agent: str
    tool: str
    arguments: dict
    channel: str
    status: str = "pending"  # pending | approved | denied
    resolution: str | None = None
    resolved_by: str | None = None
```

**Routes:**
```
POST   /api/tool_approvals/request     → agent requests approval
GET    /api/tool_approvals/pending      → list pending approvals
POST   /api/tool_approvals/{id}/approve → approve
POST   /api/tool_approvals/{id}/deny    → deny
```

**Legacy ref:** `tool_approvals.py` — same concept, same flow

### Depends On
PR #10 (WebSocket for real-time approval prompts)

### Verification
- Request approval via API — appears in pending list
- Approve — status changes, WebSocket broadcasts
- Deny — status changes
- `pytest` passes

---

## PR #20: Jobs system — model + store + service + routes

### Goal
Add bounded work containers (jobs/tasks) that agents can be assigned to.

### Scope
- `backend/src/duckdome/models/job.py` — Job model
- `backend/src/duckdome/stores/job_store.py` — JSONL persistence
- `backend/src/duckdome/services/job_service.py` — create, update, assign, close
- `backend/src/duckdome/routes/jobs.py` — REST endpoints
- `backend/tests/test_jobs.py` — tests

### Changes

**Model:**
```python
class Job(BaseModel):
    id: str
    title: str
    body: str = ""
    status: str = "open"  # open | done | archived
    channel: str
    assignee: str | None = None
    created_by: str
    messages: list[dict] = []
    created_at: float
    updated_at: float
```

**Routes:**
```
GET    /api/jobs                       → list jobs (filter by channel, status)
POST   /api/jobs                       → create job
PATCH  /api/jobs/{id}                  → update job
GET    /api/jobs/{id}/messages         → list job messages
POST   /api/jobs/{id}/messages         → post message to job
```

**Legacy ref:** `jobs.py` — same concept, drop reorder and delete (archive instead)

### Depends On
PR #10 (WebSocket)

### Verification
- Create job, assign to agent, add messages, close — full lifecycle
- List jobs filtered by status
- WebSocket broadcasts job changes
- `pytest` passes

---

## Summary: PR Dependency Graph

```text
PR #8  (runner visibility — IN REVIEW)
  └── PR #9  (message type field)
        └── PR #10 (WebSocket backend)
              ├── PR #11 (WebSocket frontend)
              ├── PR #12 (loop guard) ← also needs PR #9
              ├── PR #16 (runner expansion)
              ├── PR #19 (tool approvals)
              └── PR #20 (jobs)
        PR #13 (MCP chat_send + chat_read) ← needs PR #10
              └── PR #14 (MCP chat_join + identity)
                    └── PR #15 (MCP HTTP transport)
        PR #17 (rules model + store) ← needs PR #9
              └── PR #18 (rules routes + MCP tool) ← needs PR #13 + #17
```

## Parallelizable Work

After PR #10 merges, these can be worked on in parallel:
- PR #11 (WebSocket frontend) + PR #13 (MCP bridge) — independent
- PR #12 (loop guard) + PR #16 (runner expansion) — independent
- PR #17 (rules) + PR #19 (tool approvals) + PR #20 (jobs) — independent
