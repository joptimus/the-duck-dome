# Reliability Layer Investigation

> **Scope:** Message delivery tracking, missed-message detection, retry/escalation, agent inbox/assignment behavior.
>
> **Legacy repo:** github.com/joptimus/agentchattr
>
> **Date:** 2026-03-28

---

## 1. Executive Summary

The legacy agentchattr system has a working message delivery pipeline — human sends message, router resolves @mentions, queue file triggers agent, agent reads via MCP, agent responds via MCP. It works well enough for the happy path.

But there is **no reliability layer**. The system cannot answer basic questions:

- Did the agent receive the message?
- Is the agent working on it?
- Has the agent finished?
- Did a message get lost?
- Should something be retried?

Delivery is fire-and-forget. There is no acknowledgment, no delivery state, no missed-message detection, no retry, and no escalation. The closest things to reliability are the loop guard (prevents runaway agent-to-agent hops), the crash timeout (deregisters agents after 60s silence), and the typing/activity indicators (agent is visibly working). But none of these answer the question "did the agent handle my request?"

DuckDome should fix this by introducing a lightweight delivery state model — not a full message bus, but enough to track whether a directed message was seen, whether a response came back, and whether the user should be alerted to a gap.

---

## 2. Legacy Behavior Audit

### 2.1 Message Send Flow

**What it does:** Human types message in UI → WebSocket sends to server → `store.add()` persists to JSONL with fsync → callback fires `_handle_new_message()` → router resolves targets → `agents.trigger()` writes queue file → broadcast to all WebSocket clients.

**Where:** `apps/server/src/app.py:910-1126` (_handle_new_message), `store.py:52-93` (add), `router.py:51-80` (get_targets), `agents.py:32-54` (trigger).

**Status:** Explicit. Well-implemented for the happy path.

**Risks:**
- Queue file writes in `agents.py` use append mode with no fsync (unlike `store.py` which does fsync). A crash between write and OS flush could lose the trigger.
- Sender extraction in trigger entry uses naive `message.split(":")[0]` — fragile.
- No idempotency — same trigger can fire twice, creating duplicate queue entries.

### 2.2 Agent Mention Routing

**What it does:** `router.get_targets()` extracts @mentions from text. For human messages: routes to mentioned agents, or falls back to `default_mention` config (default: "none"). For agent messages: only routes on explicit @mention, increments hop counter.

**Where:** `apps/server/src/router.py:51-80` (get_targets), `router.py:33-46` (parse_mentions).

**Status:** Explicit. Clean state machine per channel.

**Risks:**
- Default routing config `default = "none"` means unmentioned messages go nowhere. This is safe but could confuse new users expecting auto-routing.
- `@both` / `@all` routing checks online status, which is a point-in-time check that could be stale by the time the trigger fires.

### 2.3 How an Agent Is Notified to Act

**What it does:** `agents.trigger()` appends a JSON entry to `{agent_name}_queue.jsonl`. The wrapper process (`wrapper.py` or `wrapper_api.py`) polls this file and injects a prompt into the agent's terminal session (via tmux send-keys on Unix, Win32 WriteConsoleInput on Windows). For API agents, the wrapper reads chat context and calls the model endpoint directly.

**Where:** `agents.py:32-54` (trigger), `wrapper.py` (CLI agent polling), `wrapper_api.py` (API agent polling), `wrapper_unix.py` (tmux injection).

**Status:** Explicit but brittle.

**Risks:**
- Queue file is append-only with no consumption tracking. No way to know if the wrapper has processed an entry.
- If wrapper is down when trigger fires, the entry sits in the queue file indefinitely. When wrapper restarts, it may or may not re-process old entries (depends on wrapper implementation).
- For CLI agents, "notification" means injecting keystrokes into a terminal — inherently fragile and platform-specific.

### 2.4 How Pending Messages Are Fetched

**What it does:** Agents call `chat_read()` via MCP tool. First call returns last N messages (full context). Subsequent calls use a per-agent, per-channel cursor to return only new messages since last read. Cursor persists to disk atomically (temp file + rename).

**Where:** `mcp_bridge.py:532-633` (chat_read), `mcp_bridge.py:523-529` (_update_cursor), `mcp_bridge.py:402-427` (cursor persistence).

**Status:** Explicit. Smart cursor system.

**Risks:**
- Cursor save happens outside the lock (`_cursors_lock` released before `_save_cursors()` called). Two rapid reads could cause a stale cursor to overwrite a newer one on disk. On restart, the agent would re-read some messages.
- No "pending count" computed anywhere. The system cannot answer "how many messages is this agent behind?"

### 2.5 Whether Delivery Is Acknowledged

**Status:** Absent.

There is no acknowledgment mechanism anywhere. When a trigger is written to the queue file, no confirmation comes back. When an agent calls `chat_read()`, the cursor advances, but this is not reported to the server as "agent has seen message X." The system has no concept of delivery confirmation.

### 2.6 Whether "Read" Is Tracked

**Status:** Implicit, partial.

Read cursors exist per-agent per-channel (`_cursors` in `mcp_bridge.py`). These track the last message ID the agent fetched. But:
- This is not surfaced to the UI. No "agent has read up to message X" indicator.
- Cursor advance happens on `chat_read()`, not on actual processing. An agent could read and then crash before acting.
- There is no "read receipt" concept for specific messages.

### 2.7 Whether "Responded" Is Inferred or Tracked

**Status:** Absent.

There is no tracking of whether an agent responded to a specific message. The `reply_to` field exists on messages but is manually set by agents — most agents don't use it. There is no automatic correlation between a trigger and the resulting response. The system cannot answer "which message was this response to?"

### 2.8 How Loop Prevention Works

**What it does:** Per-channel state machine with `hop_count`, `paused`, `guard_emitted`. Every agent-to-agent @mention increments `hop_count`. When `hop_count > max_hops` (default 4), routing is paused and a system message is posted ("Loop guard: 4 agent-to-agent hops reached. Type /continue to resume."). Human messages reset all state. Manual `/continue` command also resets.

**Where:** `router.py:51-96` (full state machine), `app.py:1088-1098` (guard message emission).

**Status:** Explicit. Well-designed.

**Risks:**
- `hop_count` is in-memory only. Server restart resets it. Not a real problem since conversations restart too.
- No per-conversation scoping — the guard is per-channel, so all conversations in a channel share the same counter.

### 2.9 How Missed or Ignored Messages Are Handled

**Status:** Absent.

There is no missed-message detection. If an agent is triggered but never responds, nothing happens. No timeout fires. No alert appears. No retry occurs. The user must notice the silence themselves.

The only related mechanism is the empty-read escalation (`mcp_bridge.py:611-623`), which warns agents to stop polling when there are no new messages. This is a resource-saving measure, not a missed-message detector.

### 2.10 Whether Retry/Escalation Exists

**Status:** Absent.

No retry mechanism exists anywhere. The word "retry" appears once in the codebase as an error message ("Re-register and retry" in `mcp_bridge.py:167`). The word "escalate" does not appear at all.

If a trigger fails (wrapper down, agent crashes mid-response, network issue), the message is silently lost. The human must notice and re-send.

### 2.11 Whether Explicit Assignment/Inbox Exists

**Status:** Absent as a first-class concept. Jobs partially fill this role.

There is no "inbox" or "assignment" model. Messages are broadcast, routed by @mention, and triggered via queue files. An agent cannot be "assigned" a message with tracking.

Jobs (`jobs.py`) are the closest thing:
- Jobs have an optional `assignee` field
- Jobs have status: open → done → archived
- Jobs have threaded messages separate from main chat
- Frontend tracks unread count per job

But jobs are bounded work containers, not a general assignment mechanism. Most messages never become jobs.

### 2.12 How UI Surfaces Agent Activity or Unread State

**What it does:** Multiple UI indicators exist:

| Indicator | Source | Location |
|-----------|--------|----------|
| Agent status pills (offline/available/working) | `broadcast_status()` every 3s | `AgentStatusBar.tsx` |
| "Is writing..." strip | `typing` WebSocket event | `ThinkingStrip.tsx` |
| Activity panel (task, file, elapsed, output) | `activity` WebSocket event | `ActivityPanel.tsx` |
| Per-channel unread badge | `channelStore.channelUnread` | `ChannelRow.tsx` |
| Per-job unread badge | `jobStore.unreadByJobId` | `JobsPanel.tsx` |
| Pending tool approvals pill | REST polling every 7s | `PendingApprovalPill.tsx` |

**Status:** Explicit but limited. The UI can show "agent is working" and "you have unread messages in this channel." It cannot show "agent was asked to do X and hasn't responded" or "this message was delivered but not acted on."

---

## 3. Legacy Gaps / Risks

### 3.1 No Delivery Confirmation

The system fires triggers and hopes they arrive. Between `agents.trigger()` writing a queue file and the agent actually processing it, there is a gap with no observability. The queue file has no consumption tracking. A dead wrapper silently drops all triggers.

### 3.2 No Response Correlation

When an agent responds, there is no automatic link to what it was responding to. The `reply_to` field is optional and rarely used. This makes it impossible to determine whether a specific request was addressed.

### 3.3 Silent Failures on Agent Crash

If an agent crashes after being triggered but before responding, nothing detects this. The crash timeout (60s) will eventually deregister the agent, and a system message will appear. But the original request is forgotten — no retry, no alert to the user that the request was not handled.

### 3.4 No Pending/Waiting State

After sending a message that @mentions an agent, the user has no way to know:
- Was the agent triggered? (No trigger confirmation)
- Has the agent read the message? (Cursor is internal)
- Is the agent working on it? (Activity indicator helps, but it's generic — not tied to a specific request)
- Has the agent finished? (No completion signal)

### 3.5 Queue File Brittleness

Queue files are append-only, never cleaned, never acknowledged. They grow indefinitely. Multiple triggers for the same agent can pile up with no deduplication. If a wrapper restarts, it may re-process old entries or skip them depending on implementation.

### 3.6 Race Conditions in Cursor Persistence

The cursor save path releases the lock before writing to disk. Two rapid `chat_read()` calls can cause a stale cursor to overwrite a newer one. On restart, the agent would re-read messages — not catastrophic but creates noise.

### 3.7 No Observability for the User

The user cannot see a timeline of "I asked X → agent was triggered → agent read it → agent responded." The activity panel shows generic task/file/elapsed information, but it's not correlated to specific messages. The typing indicator shows "agent is writing" but not "agent is writing in response to your message about X."

---

## 4. Proposed DuckDome Reliability Model

### 4.1 Design Principles

1. **Track directed messages, not all messages.** Only messages that @mention an agent or are assigned to one need delivery tracking. Broadcast messages don't.
2. **States, not queues.** Use delivery states on messages rather than building a separate message queue. The message store already exists — extend it.
3. **Observable timeline.** The user should see the lifecycle of a directed message without digging.
4. **Timeouts, not retries.** Auto-retry is dangerous with AI agents (could cause duplicate work). Instead, detect missed messages and alert the user, letting them decide.
5. **Solo-developer friendly.** No distributed systems patterns. No eventual consistency. One process, one store, simple state transitions.

### 4.2 Delivery State Model

Each directed message (one that targets a specific agent) gets a delivery state:

```
sent → delivered → acknowledged → resolved
                                 ↘ timeout
```

| State | Meaning | Transition |
|-------|---------|------------|
| `sent` | Message stored and trigger dispatched | Automatic on send |
| `delivered` | Agent has fetched this message via `chat_read()` | When cursor advances past this message ID |
| `acknowledged` | Agent has sent a response (linked via `reply_to` or within time window) | When agent sends a message in the same channel after reading |
| `resolved` | User has dismissed or marked as handled | Manual user action |
| `timeout` | Expected response time exceeded with no acknowledgment | Timer-based, configurable |

**Important:** Only messages with explicit @mention targets get tracked. Regular chat messages do not.

### 4.3 Event Flow

```
1. User sends "@claude review this PR"
2. Server creates message with delivery_state: {
     target: "claude",
     state: "sent",
     sent_at: <timestamp>
   }
3. agents.trigger("claude", ...) fires
4. Claude calls chat_read() and cursor advances past message
   → delivery_state.state = "delivered", delivered_at = <timestamp>
5. Claude sends a response (with or without reply_to)
   → delivery_state.state = "acknowledged", acknowledged_at = <timestamp>
   → response_id links to Claude's reply
6. If step 4 or 5 doesn't happen within timeout:
   → delivery_state.state = "timeout"
   → UI shows alert: "Claude hasn't responded to your message"
```

### 4.4 Minimum Data Model

**On the message record (extend existing message schema):**

```python
# Only present on messages with @mention targets
"delivery": {
    "target": "claude",           # which agent this was directed to
    "state": "sent",              # sent | delivered | acknowledged | resolved | timeout
    "sent_at": 1711612800.0,
    "delivered_at": null,         # set when agent reads past this ID
    "acknowledged_at": null,      # set when agent responds
    "response_id": null,          # ID of the agent's response message
    "timeout_s": 120,             # configurable per-message or global default
}
```

**No new tables or stores.** This is a field on existing messages. Persists with the message in JSONL.

**For multiple targets** (e.g., `@claude @codex`), create one delivery entry per target:

```python
"deliveries": [
    {"target": "claude", "state": "sent", ...},
    {"target": "codex", "state": "sent", ...},
]
```

### 4.5 What Should Be Shown in UI

**Per-message delivery indicator (inline):**
- Small icon/badge on directed messages showing current state
- Sent: neutral dot
- Delivered: checkmark (agent has read)
- Acknowledged: double checkmark or "replied" tag with link to response
- Timeout: warning icon with "No response" label

**Timeline/attention panel (optional, v2):**
- List of all directed messages with pending/timeout state
- Filterable by agent
- One-click "re-send" or "dismiss"

**Topbar indicator (v1):**
- Badge showing count of timed-out messages: "2 unanswered"
- Clicking opens a filtered view

### 4.6 What Should Stay Out of v1

- **Auto-retry.** Too dangerous with AI agents. User should decide.
- **Escalation rules.** "If Claude doesn't respond, ask Codex" — cool but complex. Defer.
- **Per-agent SLA configuration.** One global timeout is enough for v1.
- **Delivery tracking for non-directed messages.** Only @mention messages get tracked.
- **Message-level priority.** Everything is equal priority in v1.
- **Inbox/assignment as a separate concept.** Use delivery tracking on messages instead. Jobs already exist for bounded work.

---

## 5. Minimum Useful v1

### What is the smallest useful version?

Track delivery state on @mention messages. Show a timeout alert when an agent doesn't respond. Let the user dismiss or re-trigger.

That's it. No retry automation. No escalation. No inbox. Just: "I asked Claude something 2 minutes ago and it hasn't responded — here's a warning."

### What should be deferred?

- Escalation chains (if agent A doesn't respond, try agent B)
- Auto-retry with backoff
- Per-agent timeout configuration
- Response quality assessment
- Assignment/inbox as a standalone feature
- Historical delivery analytics

### What would be too much for v1?

- A separate delivery queue service
- A state machine library
- Websocket-based real-time delivery state streaming (just poll/refresh)
- Per-message timeout configuration UI
- Multi-step escalation workflows

---

## 6. Recommended Implementation Slices

### Slice 1: Delivery State on Directed Messages

**Purpose:** Track whether an @mentioned agent has received and responded to a message.

**Includes:**
- Add `delivery` field to message schema for @mention messages
- Set state to `sent` when message is created with a resolved target
- Transition to `delivered` when agent's cursor advances past the message ID in `chat_read()`
- Transition to `acknowledged` when agent sends a message in the same channel (with or without `reply_to`) after having read the directed message
- Persist delivery state changes to disk (update message record or sidecar file)
- Backend API endpoint: `GET /api/deliveries?state=sent&state=delivered` to query pending deliveries

**Intentionally does not include:**
- Timeout detection (slice 2)
- UI indicators (slice 3)
- Retry or escalation
- Multi-target tracking (start with single target per message)

**Dependencies:** Existing message store, existing cursor system.

**Acceptance criteria:**
- Sending `@claude do X` creates a message with `delivery.state = "sent"`
- When Claude calls `chat_read()` and receives that message, state transitions to `"delivered"`
- When Claude sends a response in the same channel, state transitions to `"acknowledged"` and `response_id` is set
- Delivery state persists across server restart
- Messages without @mentions have no delivery field

### Slice 2: Timeout Detection and Backend Alerts

**Purpose:** Detect when a directed message has not been acknowledged within a configurable time, and surface this as a queryable state.

**Includes:**
- Global configurable timeout (default: 120s) in backend config
- Background check (runs every 10-15s) that scans `sent` and `delivered` messages older than timeout
- Transition timed-out messages to `state: "timeout"`
- Emit a system event/broadcast when a message times out (so frontend can react)
- `POST /api/deliveries/{msg_id}/dismiss` — user marks a timeout as resolved
- `POST /api/deliveries/{msg_id}/retry` — user re-triggers the agent for this message

**Intentionally does not include:**
- Auto-retry (user must click)
- Escalation to different agents
- Per-agent or per-message timeout config
- UI rendering (slice 3)

**Dependencies:** Slice 1 (delivery state model).

**Acceptance criteria:**
- A `sent` message older than timeout transitions to `"timeout"`
- A `delivered` message older than timeout transitions to `"timeout"`
- Timeout state is broadcast to connected clients
- User can dismiss a timeout (state → `"resolved"`)
- User can retry a timeout (re-triggers agent, state → `"sent"` with new timestamp)
- A message that gets acknowledged before timeout never transitions to timeout

### Slice 3: UI Delivery Indicators

**Purpose:** Show the user the delivery lifecycle of directed messages inline and surface attention-needed items.

**Includes:**
- Per-message delivery badge: sent (dot), delivered (check), acknowledged (double-check + link to response), timeout (warning)
- Topbar "unanswered" pill showing count of timed-out messages
- Clicking the pill filters/scrolls to timed-out messages
- Inline "Retry" and "Dismiss" buttons on timed-out messages
- State updates via WebSocket broadcast (react to delivery state changes in real-time)

**Intentionally does not include:**
- Separate attention/inbox panel (defer to v2)
- Historical delivery metrics
- Per-agent delivery success rates
- Notification sounds for timeouts

**Dependencies:** Slice 1 + Slice 2 (delivery state + timeout detection).

**Acceptance criteria:**
- Directed messages show delivery state inline
- Timed-out messages are visually distinct (warning icon)
- "Unanswered" pill in topbar shows correct count
- Clicking "Retry" re-triggers the agent and resets delivery state
- Clicking "Dismiss" marks as resolved and removes from unanswered count
- Delivery state updates appear in real-time without page refresh

---

## 7. Open Questions / Ambiguities

### From the legacy code:

1. **Queue file consumption:** The wrapper's queue polling logic was not fully inspected (it's in the platform-specific `wrapper_unix.py` / `wrapper_windows.py` files). It's unclear whether old queue entries are replayed on wrapper restart or skipped. This affects whether DuckDome needs deduplication.

2. **Multi-target delivery:** If a message @mentions two agents (`@claude @codex`), should both get independent delivery tracking? The proposed model supports this but slice 1 defers it. Need to decide when to add it.

3. **Job-scoped messages:** Messages within jobs (`job_id != 0`) go through `chat_send` with job-scoped storage. Should delivery tracking apply to job messages too, or only main chat? Jobs already have their own status model.

4. **Session-scoped messages:** The session engine has its own turn-based orchestration with explicit "waiting on agent X" state (`session_engine.py:223-272`). This overlaps with delivery tracking. Should sessions use the delivery model, or keep their own state?

5. **What counts as "acknowledged"?** If Claude reads a message and then sends an unrelated message in the same channel, should that count as acknowledgment? Strict `reply_to` matching is more accurate but most agents don't set it. Time-window-based correlation (agent responded within N seconds of reading) is more practical but imprecise.

6. **"Delivered" vs. "read":** The cursor advance means the message was included in a `chat_read()` response. But the agent may not have processed it — it might have been in a batch of 20 messages and the agent focused on a different one. "Delivered" is the honest term; "read" overpromises.

### For DuckDome design:

7. **Where to store delivery state:** Inline on the message record (simple, single source of truth) vs. sidecar store (avoids rewriting JSONL). Inline is simpler but requires JSONL update-in-place or rewrite, which the current store doesn't support (it's append-only). A sidecar `deliveries.json` keyed by message ID may be more practical.

8. **Timeout granularity:** 120s default is a guess. Some agent tasks take 30 seconds, others take 10 minutes. A single timeout may cause false positives. Consider: timeout based on agent's historical response time, or user-adjustable per-send.

9. **Interaction with loop guard:** If the loop guard pauses routing and a directed message times out, should the timeout alert tell the user "routing was paused"? Otherwise the user might think the agent failed when it was actually blocked.
