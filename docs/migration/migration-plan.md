# AgentChattr → DuckDome Migration Plan

> **Date:** 2026-03-29
> **Source repo:** agentchattr (C:\Users\James\Dev\agentchattr)
> **Target repo:** the-duck-dome (C:\Users\James\Dev\the-duck-dome)
> **Current DuckDome phase:** Phase 2-3 (Core Runtime Spine + Reliability Layer in progress)

---

## 1. Executive Summary

DuckDome is a clean rewrite of agentchattr — a local multi-agent chat coordination system. The migration strategy is **migrate by capability, not by folder**. This document maps every agentchattr feature to its DuckDome status (done, in-progress, not started, intentionally dropped) and provides an ordered implementation plan for remaining work.

### Current State at a Glance

| Category | agentchattr Features | DuckDome Done | In Progress | Not Started | Dropped |
|----------|---------------------|---------------|-------------|-------------|---------|
| Core Chat | 12 | 3 | 1 | 7 | 1 |
| Agent Management | 9 | 4 | 0 | 4 | 1 |
| Reliability | 0 (gap) | 5 | 1 | 1 | 0 |
| Rules System | 7 | 0 | 0 | 5 | 2 |
| Jobs/Tasks | 7 | 0 | 0 | 5 | 2 |
| Schedules | 5 | 0 | 0 | 0 | 5 |
| Sessions | 7 | 0 | 0 | 4 | 3 |
| Tool Approvals | 4 | 0 | 0 | 4 | 0 |
| MCP Integration | 6 | 0 | 0 | 6 | 0 |
| Repository Mgmt | 5 | 2 | 0 | 2 | 1 |
| UI/UX | 80+ | 3 | 0 | 75+ | 2 |
| Electron/Desktop | 4 | 2 | 0 | 1 | 1 |
| Export/Import | 2 | 0 | 0 | 2 | 0 |
| Security | 2 | 0 | 0 | 2 | 0 |

---

## 2. Feature-by-Feature Comparison

### 2.1 Core Chat System

| Feature | agentchattr | DuckDome Status | Notes |
|---------|------------|-----------------|-------|
| Multi-channel messaging | String-based channels in JSONL | **DONE** — First-class Channel model (GENERAL/REPO) with UUID IDs | Improved: channels are typed objects, not plain strings |
| @mention routing | `router.py` with hop counter | **DONE** — `message_service.py` regex mention detection, channel-scoped filtering | Improved: mentions filtered to channel-registered agents only |
| Message persistence (JSONL) | `store.py` append-only with fsync | **DONE** — `message_store.py` append-only JSONL with fsync | Same pattern, cleaner implementation |
| Message send/receive flow | `app.py` WebSocket broadcast + REST | **PARTIAL** — Backend REST API exists for send/list. Frontend NOT wired to backend — uses local state + mock data only | WebSocket NOT implemented — see gap. Frontend sends not connected to API |
| Message type taxonomy | 10+ types: chat, system, join, leave, rule_proposal, job_proposal, job_created, session_draft, session_end, decision | **NOT STARTED** — Message model has no `type` field | CRITICAL: Must add before rules/jobs/sessions. Enables system messages, proposal cards, breadcrumbs |
| `@all`/`@both` mention keywords | `router.py` expands to all online agents | **NOT STARTED** | Need keyword expansion in mention parsing |
| Message threading (reply_to) | `reply_to` field on messages | **NOT STARTED** | Need to add `reply_to` field to Message model |
| Message editing | PATCH /api/messages/{id} | **NOT STARTED** | Need edit route + store update |
| Message deletion | DELETE + bulk delete | **NOT STARTED** | Need delete route + store support |
| Todo markers on messages | `todos.json` sidecar | **NOT STARTED** | Defer — low priority (P2) |
| File attachments/uploads | `/api/upload`, 10MB max, `uploads/` dir | **NOT STARTED** | Need upload endpoint + file serving |
| WebSocket real-time updates | `WS /ws` with 50+ event types | **NOT STARTED** | Critical gap — required for real-time UX |

### 2.2 Agent Management

| Feature | agentchattr | DuckDome Status | Notes |
|---------|------------|-----------------|-------|
| Agent registry | Global `agents.json` config | **DONE** — Per-channel AgentInstance model | Improved: channel-scoped, not global |
| Agent status (online/offline/working) | `broadcast_status()` every 3s | **DONE** — AgentInstance.status field with heartbeat tracking | Same concept, cleaner model |
| Agent heartbeat | POST /api/heartbeat/{name} | **DONE** — POST /api/agents/heartbeat | Same behavior |
| Agent registration/deregistration | POST /api/register, /api/deregister | **DONE** — POST /api/agents/register, /deregister | Same behavior |
| Agent roles (reviewer, builder, etc.) | `roles.json`, POST /api/roles | **NOT STARTED** | Need roles field on AgentInstance + role assignment API |
| Agent custom avatars ("hats") | `hats.json`, SVG storage | **NOT STARTED** | Low priority (P2), cosmetic |
| Agent renaming (instances) | POST /api/rename-agent | **DROPPED** | DuckDome uses agent_type per channel — no slot naming |
| Multi-instance agents | Slot-based naming (claude-1, claude-2) | **NOT STARTED** | Deferred — may need rethinking for channel-scoped model |
| Agent identity claim system | `registry.claim()` with family-based matching, pending/active states, rename chains | **NOT STARTED** | Legacy has sophisticated claim flow important for MCP reconnection. DuckDome has simple register/deregister |

### 2.3 Reliability Layer (NEW in DuckDome)

| Feature | agentchattr | DuckDome Status | Notes |
|---------|------------|-----------------|-------|
| Delivery state tracking | ABSENT | **DONE** — Delivery model with SENT/SEEN/RESPONDED/TIMEOUT states | Major improvement over legacy |
| Delivery state transitions | ABSENT | **DONE** — mark_seen, mark_responded, process_agent_read, process_agent_response | Full state machine |
| Open delivery queries | ABSENT | **DONE** — GET /api/deliveries?state=open | New capability |
| Trigger queue (FIFO) | File-based queue (`*_queue.jsonl`) | **DONE** — Trigger model with PENDING/CLAIMED/COMPLETED/FAILED, dedupe_key | Major improvement: structured, deduplicated |
| Trigger claiming + completion | ABSENT (fire-and-forget) | **DONE** — claim_trigger, complete_trigger, fail_trigger | New capability |
| Timeout detection | ABSENT | **IN PROGRESS** — Model supports TIMEOUT state, background checker not yet built | Slice 2 from reliability plan |
| UI delivery indicators | ABSENT | **NOT STARTED** | Slice 3 from reliability plan |

### 2.4 Loop Guard

| Feature | agentchattr | DuckDome Status | Notes |
|---------|------------|-----------------|-------|
| Per-channel hop counter | `router.py` in-memory state machine | **NOT STARTED** | Need to port: hop_count, max_hops, paused state, /continue command |
| Loop guard system message | Auto-posted when max hops reached | **NOT STARTED** | Need system message type + auto-post |
| Human message resets counter | Implicit in router logic | **NOT STARTED** | Part of loop guard implementation |

### 2.5 Rules System

| Feature | agentchattr | DuckDome Status | Notes |
|---------|------------|-----------------|-------|
| Shared rules store | `rules.json` with epoch versioning | **NOT STARTED** | Need Rule model, RuleStore, RuleService |
| Rule proposals (agents propose) | POST /api/rules with status: draft | **NOT STARTED** | Need proposal flow in UI |
| Rule activation/deactivation | POST /api/rules/{id}/activate | **NOT STARTED** | Need status transitions |
| Rule freshness/epoch checking | GET /api/rules/freshness | **NOT STARTED** | Needed for MCP agent cache |
| Rule reminders to agents | POST /api/rules/remind | **NOT STARTED** | Depends on MCP bridge |
| Rule reordering (drag-drop) | POST /api/rules/reorder | **DROPPED** | Simplify: rules are equal priority |
| Max 10 active rules limit | Enforced server-side | **DROPPED** | Simplify: no arbitrary limit |

### 2.6 Jobs/Tasks System

| Feature | agentchattr | DuckDome Status | Notes |
|---------|------------|-----------------|-------|
| Job CRUD | `jobs.json`, full REST API | **NOT STARTED** | Need Job model, store, service, routes |
| Job assignment to agents | `assignee` field | **NOT STARTED** | May merge with trigger/inbox model |
| Job threaded messages | Separate message list per job | **NOT STARTED** | Need job-scoped message store |
| Job status (open/done/archived) | Status field + transitions | **NOT STARTED** | Need status flow |
| Job proposals (message → job) | POST /api/messages/{id}/demote | **NOT STARTED** | Need conversion flow |
| Job reordering (drag-drop) | POST /api/jobs/reorder | **DROPPED** | Simplify |
| Job deletion | DELETE /api/jobs/{id} | **DROPPED** | Archive instead of delete |

### 2.7 Scheduled Prompts

| Feature | agentchattr | DuckDome Status | Notes |
|---------|------------|-----------------|-------|
| Recurring prompts | `schedules.json`, interval + daily_at | **DROPPED (deferred)** | Complex, defer to Phase 6+ |
| One-shot schedules | send_at timestamp | **DROPPED (deferred)** | Defer |
| Pause/resume | paused field | **DROPPED (deferred)** | Defer |
| Multiple targets | targets[] array | **DROPPED (deferred)** | Defer |
| Natural language parsing | "every 30m", "daily at 09:00" | **DROPPED (deferred)** | Defer |

### 2.8 Sessions / Modes

| Feature | agentchattr | DuckDome Status | Notes |
|---------|------------|-----------------|-------|
| Session engine (multi-phase) | `session_engine.py` + `session_store.py` | **NOT STARTED** | Simplify to "modes" (Review, Debate, Build) |
| Built-in templates (debate, review, etc.) | 4 JSON templates | **NOT STARTED** | Keep 3-4 simplified templates |
| Custom user templates | `custom_templates.json` | **NOT STARTED** | Defer to Phase 6 |
| Phase progression | Auto-trigger based on roles | **NOT STARTED** | Simplify: manual phase advance |
| Dissent mandate for critics | Prompt injection for reviewer role | **DROPPED** | Over-engineered for v1 |
| Session state tracking | active/complete/interrupted | **DROPPED** | Simplify: modes are stateless toggles |
| Output message marking | `is_output` flag on phase | **DROPPED** | Simplify |

### 2.9 Tool Approvals

| Feature | agentchattr | DuckDome Status | Notes |
|---------|------------|-----------------|-------|
| Per-agent tool policies | `tool_approvals.json`, allow/deny | **NOT STARTED** | Phase 4 — Human Control Layer |
| Pending approval UI | ToolApprovalCard in chat | **NOT STARTED** | Need approval request flow |
| Bulk approval | Approve all from agent | **NOT STARTED** | Need bulk action |
| Policy persistence | Remember decisions | **NOT STARTED** | Need ToolApprovalStore |

### 2.10 MCP Integration

| Feature | agentchattr | DuckDome Status | Notes |
|---------|------------|-----------------|-------|
| MCP bridge (FastMCP server) | `mcp_bridge.py` — chat_send, chat_read, chat_join, chat_rules, chat_claim | **NOT STARTED** | Phase 5 — Critical for agent connectivity |
| MCP HTTP transport (port 8200) | Streamable HTTP for Claude/Codex/Qwen | **NOT STARTED** | Need MCP server setup |
| MCP SSE transport (port 8201) | SSE for Gemini | **NOT STARTED** | Need SSE endpoint |
| MCP proxy identity | `mcp_proxy.py` — agent identity verification | **NOT STARTED** | Security requirement |
| MCP cursor system | Per-agent, per-channel read cursors | **NOT STARTED** | Port cursor logic from legacy |
| Token-aware rate limiting | Prevents excessive chat_read calls | **NOT STARTED** | Port from mcp_bridge.py |

### 2.11 Repository Management

| Feature | agentchattr | DuckDome Status | Notes |
|---------|------------|-----------------|-------|
| Repo-type channels | Channel bound to git repo path | **DONE** — ChannelType.REPO with repo_path validation | Same concept, cleaner model |
| Repo path validation | Check path exists + is dir | **DONE** — channel_service.create_channel validates | Same behavior |
| Auto-discovery of repos | Scan root for .git directories | **NOT STARTED** | Need repo scanner service |
| Repo sources (watched roots) | `repo_sources.json` | **NOT STARTED** | Need source management |
| Hidden repos | `repo_hidden.json` | **DROPPED** | Simplify: user just doesn't create channels for unwanted repos |

### 2.12 Settings & Configuration

| Feature | agentchattr | DuckDome Status | Notes |
|---------|------------|-----------------|-------|
| Room settings (title, username) | `settings.json`, GET/PATCH /api/settings | **NOT STARTED** | Need settings model + API |
| config.toml (server config) | Agent definitions, ports, routing defaults | **NOT STARTED** | Need equivalent config |
| config.local.toml (user overrides) | API agent definitions | **NOT STARTED** | Need local override mechanism |
| Font/contrast preferences | `font`, `contrast` in settings | **NOT STARTED** | Low priority (P2) |
| Max channels config | `max_channels` setting | **DROPPED** | Unnecessary limit |

### 2.13 UI Components

| Feature | agentchattr | DuckDome Status | Notes |
|---------|------------|-----------------|-------|
| Chat timeline (virtualized) | react-window based ChatTimeline | **PARTIAL** — ChatShell renders messages, not virtualized | Need virtualization for large histories |
| Chat bubble per message | ChatBubble with MessageHeader/Content/Toolbar | **PARTIAL** — Basic message display in ChatShell | Need richer message rendering |
| Sidebar channel list | ChannelList + ChannelRow | **DONE** — SidebarChannelList component | Basic version working |
| Channel create modal | ChannelCreateModal | **DONE** — ChannelCreateModal component | Working |
| Agent status strip | AgentStatusBar | **DONE** — AgentRuntimeStrip + RuntimeDetailsPanel | Improved with detail panel |
| Message composer | Composer with MentionMenu + SlashMenu | **NOT STARTED** | Need rich composer with @mention autocomplete |
| Mention autocomplete | MentionMenu popup | **NOT STARTED** | Need @mention popup |
| Slash command menu | SlashMenu popup | **NOT STARTED** | Defer — Phase 6 |
| Reply context display | ReplyContext above composer | **NOT STARTED** | Depends on reply_to support |
| Attachment preview | AttachmentPreview in composer | **NOT STARTED** | Depends on upload support |
| Image lightbox | ImageLightbox modal | **NOT STARTED** | Low priority |
| Export/import modal | ExportImportModal | **NOT STARTED** | Phase 6 |
| Help modal | HelpModal | **NOT STARTED** | Low priority |
| Visual effects (particles, orbs) | ParticleField, AmbientOrbs | **DROPPED** | Not carrying over cosmetic effects |
| Zustand state management | 13 Zustand stores + index barrel | **NOT STARTED** | Need state management for frontend (currently using local state) |
| Activity panel | ActivityPanel.tsx — task/file/elapsed/output | **NOT STARTED** | Real-time agent activity display |
| Pinned messages sidebar | PinnedMessages.tsx — todo cycling (not-pinned→todo→done→cleared) | **NOT STARTED** | More than just todo markers — includes sidebar panel |

> **Note on UI scope:** The legacy frontend contains ~80+ components across chat (18), composer (9), modals (7), panels (8 sections with 20+ sub-components), sidebar (8), topbar (6), shared utilities (15), layouts (4), effects (3), and platform modules (5). The DuckDome frontend currently has ~8 components. This is the largest single area of remaining work.

### 2.14 Security & Authentication

| Feature | agentchattr | DuckDome Status | Notes |
|---------|------------|-----------------|-------|
| Session token authentication | `_install_security_middleware` — X-Session-Token header validation on all API/WS calls | **NOT STARTED** | IMPORTANT: Without this, any local process can impersonate users/agents. Must add before MCP bridge (Phase 5) |
| Decision resolution workflow | POST /api/messages/{msg_id}/resolve_decision — structured approval embedded in messages | **NOT STARTED** | Need decision message type + resolution flow |

### 2.15 Platform & Operational

| Feature | agentchattr | DuckDome Status | Notes |
|---------|------------|-----------------|-------|
| Platform detection | GET /api/platform — returns OS info | **NOT STARTED** | Low priority, useful for cross-platform behavior |
| Path opening | POST /api/open-path — open files/folders in OS | **NOT STARTED** | Convenience feature |
| Version check | GET /api/version_check — checks GitHub releases | **NOT STARTED** | Defer to Phase 8 |
| Per-repo agent subprocess management | `room_agent_manager.py` — auto-launches agent instances per repo channel with idle timeout | **NOT STARTED** | Complex subprocess lifecycle. DuckDome runner is simpler one-shot model. Must decide: port or redesign |

### 2.16 Specialized Chat Renderers (Legacy UI)

The legacy frontend has ~10 specialized in-chat card components that render different message types. These are NOT listed in the generic "UI Components" section because they are tightly coupled to specific feature systems:

| Renderer | Renders | Depends On |
|----------|---------|-----------|
| RuleProposalCard | Rule proposals inline in chat | Rules system + message types |
| JobCreatedCard | Job creation breadcrumbs | Jobs system + message types |
| SessionDraftCard | Session draft proposals | Sessions system + message types |
| DecisionCard | Decision proposals with approve/reject | Decision workflow + message types |
| ToolApprovalCard | Tool approval requests | Tool approvals + message types |
| SystemMessage | Join/leave/loop-guard/system events | Message type taxonomy |
| SummaryMessage | Channel summaries | Summary system |
| SessionBanner | Active session phase indicators | Sessions system |
| ReplyThread | Threaded reply context | Threading (reply_to) |
| AttachmentRenderer | Images and file attachments | Upload system |

**ALL of these require the message type field to be added to the Message model first.**

### 2.17 Electron / Desktop

| Feature | agentchattr | DuckDome Status | Notes |
|---------|------------|-----------------|-------|
| Electron shell | `desktop/main.js` | **DONE** — `apps/desktop/src/main.js` | Working |
| Backend auto-start | Server start from Electron | **DONE** — `apps/desktop/src/backend.js` spawns uvicorn | Working |
| Tray + notifications | Desktop notifications when unfocused | **NOT STARTED** | Defer — Phase 8 |
| Platform batch launchers | Windows .bat, macOS .sh scripts | **DROPPED** | Electron owns startup |

---

## 3. Critical Gaps (Must Fix Before Usable)

These are blockers that prevent DuckDome from functioning as a real multi-agent coordination system:

### Gap 1: WebSocket Real-Time Updates
**Impact:** Without WebSocket, the UI cannot show real-time messages, agent status changes, or delivery state updates. Users must manually refresh.

**agentchattr implementation:** `WS /ws` endpoint in `app.py`, 50+ event types, WebSocket connection manager with reconnection logic in `ws.ts`.

**DuckDome requirement:** Add WebSocket endpoint, broadcast new messages + delivery state changes + agent status updates. Frontend needs WebSocket client with reconnection.

**Estimated scope:** Backend WS endpoint + event broadcasting, frontend connection manager + event handlers.

### Gap 2: MCP Bridge
**Impact:** Without MCP, agents cannot connect to DuckDome. The entire purpose of the system requires agents to send/read messages via MCP tools.

**agentchattr implementation:** `mcp_bridge.py` (1000+ lines) — FastMCP server exposing chat_send, chat_read, chat_join, chat_rules, chat_claim tools over HTTP (port 8200) and SSE (port 8201).

**DuckDome requirement:** Rebuild MCP bridge with clean architecture. Minimum tools: chat_send, chat_read, chat_join. Use existing message/delivery APIs internally.

**Estimated scope:** MCP server module, tool definitions, transport setup, agent identity verification.

### Gap 3: Loop Guard
**Impact:** Without loop guard, agent-to-agent @mentions can create infinite routing loops, consuming resources and creating noise.

**agentchattr implementation:** `router.py` — per-channel state machine with hop_count, max_hops (default 4), paused flag, guard message.

**DuckDome requirement:** Add loop guard to message routing in message_service.py. Track hop count per channel. System message when guard triggers.

**Estimated scope:** Small — add state tracking to MessageService, system message emission.

### Gap 4: Runner Integration with Multiple Agents
**Impact:** Currently only Claude CLI is supported as a runner. Need to support Codex, Gemini, and API-based agents.

**agentchattr implementation:** Separate wrapper scripts per agent type (`wrapper.py`, `wrapper_api.py`), config-driven agent definitions.

**DuckDome requirement:** Extend runner module with pluggable executors. At minimum: Claude CLI, Codex CLI, Gemini CLI, generic API agent.

**Estimated scope:** Runner factory pattern, per-agent executor implementations, config-driven agent registration.

---

## 4. Implementation Plan (Ordered by Priority)

### Phase 3 Completion — Reliability Layer (Current)

#### 3.1 Timeout Detection (1-2 days)
- Background task that scans SENT/SEEN deliveries older than threshold
- Transition to TIMEOUT state
- Configurable global timeout (default: 120s)
- System event broadcast on timeout
- **Legacy ref:** ABSENT in agentchattr — new capability
- **Files:** New `backend/src/duckdome/services/timeout_service.py`, tests
- **Depends on:** Delivery state model (done)

#### 3.2 Dismiss/Retry Endpoints (1 day)
- POST /api/deliveries/{msg_id}/dismiss → state: RESOLVED
- POST /api/deliveries/{msg_id}/retry → re-trigger agent, state: SENT
- **Legacy ref:** ABSENT — new capability
- **Files:** Extend `deliveries.py` routes
- **Depends on:** Timeout detection

#### 3.3 UI Delivery Indicators (2-3 days)
- Per-message delivery badge (dot/check/double-check/warning)
- Topbar "unanswered" pill with count
- Inline retry/dismiss buttons on timed-out messages
- **Legacy ref:** ABSENT — new UI
- **Files:** New frontend components
- **Depends on:** Timeout detection + dismiss/retry endpoints

---

### Phase 3.5 — WebSocket Layer (Critical Gap)

#### 3.5.1 Backend WebSocket Endpoint (2-3 days)
- WS /ws endpoint with connection manager
- Broadcast events: new_message, delivery_state_change, agent_status_change, trigger_state_change
- Connection lifecycle (connect, disconnect, reconnect token)
- **Legacy ref:** `app.py:160-280` WebSocket handler, `app.py:95-135` ConnectionManager
- **Key difference:** DuckDome events are structured and typed; legacy used ad-hoc event names
- **Files:** New `backend/src/duckdome/routes/websocket.py`, connection manager module
- **Depends on:** Core message/delivery/agent services (done)

#### 3.5.2 Frontend WebSocket Client (2-3 days)
- WebSocket connection manager with reconnection + exponential backoff
- Event bus for decoupled event handling
- Hook into existing UI state to update on events
- **Legacy ref:** `apps/web/src/api/ws.ts` (WebSocket), `apps/web/src/api/types.ts` (event types)
- **Files:** New `apps/web/src/api/ws.js`, update ChannelShell to use real-time updates
- **Depends on:** Backend WebSocket endpoint

---

### Phase 4 — Human Control Layer

#### 4.1 Loop Guard (1-2 days)
- Per-channel hop counter in MessageService
- Max hops config (default: 4)
- System message on guard trigger
- Human message resets counter
- /continue command support
- **Legacy ref:** `router.py:51-96` full state machine, `app.py:1088-1098` guard message
- **Files:** Extend `message_service.py`, add system message type to Message model
- **Depends on:** Message routing (done)

#### 4.2 Rules System (3-4 days)
- Rule model: id, text, status (draft/active/archive), author, reason
- RuleStore (JSONL) with epoch versioning
- RuleService: propose, activate, deactivate, list active, check freshness
- API routes: GET/POST /api/rules, PATCH /api/rules/{id}, POST /api/rules/{id}/activate
- Frontend: rules panel with proposal cards
- **Legacy ref:** `rules.py` (300+ lines), `app.py` rule routes
- **Key simplification:** Drop reorder, drop max-10 limit, drop rule reminders (add with MCP later)
- **Files:** New models/rule.py, stores/rule_store.py, services/rule_service.py, routes/rules.py
- **Depends on:** WebSocket (for real-time rule updates)

#### 4.3 Tool Approvals (3-4 days)
- ToolApproval model: id, agent, tool, arguments, status, resolution
- ToolApprovalStore (JSONL)
- ToolApprovalService: request, approve, deny, set_policy
- API routes for approval workflow
- Frontend: approval cards in chat, pending count badge
- **Legacy ref:** `tool_approvals.py` (200+ lines), `app.py` approval routes
- **Files:** New models/tool_approval.py, stores/tool_approval_store.py, services/tool_approval_service.py, routes/tool_approvals.py
- **Depends on:** WebSocket (for real-time approval prompts)

#### 4.4 Settings System (1-2 days)
- Settings model: title, username, agent config
- SettingsStore (single JSON file)
- GET/PATCH /api/settings
- Frontend settings panel
- **Legacy ref:** `settings.json`, `app.py` settings routes
- **Files:** New models/settings.py, stores/settings_store.py, routes/settings.py
- **Depends on:** Nothing — standalone

---

### Phase 5 — MCP and Agent Management (Critical Gap)

#### 5.1 MCP Bridge Core (5-7 days)
- FastMCP server setup with tool definitions
- Minimum tools:
  - `chat_send(text, channel)` — post message via MessageService
  - `chat_read(channel, since_id?)` — read messages, advance cursor
  - `chat_join(channel)` — register agent in channel
  - `chat_rules()` — list active rules
- Per-agent cursor tracking (cursor_store.py)
- Agent identity from MCP session
- **Legacy ref:** `mcp_bridge.py` (1000+ lines) — port core logic, drop complexity
- **Key simplification:** Use existing REST services internally, don't duplicate logic
- **Files:** New `backend/src/duckdome/mcp/` module (bridge.py, cursor_store.py)
- **Depends on:** Message service, rules service, agent registry

#### 5.2 MCP Transports (2-3 days)
- HTTP transport on configurable port (default 8200)
- SSE transport on configurable port (default 8201)
- Transport selection per agent type in config
- **Legacy ref:** `mcp_bridge.py` transport setup, `config.toml` MCP section
- **Files:** Extend MCP module with transport config
- **Depends on:** MCP Bridge Core

#### 5.3 MCP Diagnostics (1-2 days)
- GET /api/mcp/status — list connected agents, transport health
- GET /api/mcp/tools — list available tools
- Frontend: MCP status panel
- **Legacy ref:** ABSENT — new capability (DuckDome differentiator)
- **Files:** New routes/mcp.py, frontend component
- **Depends on:** MCP Bridge Core

#### 5.4 Agent Runner Expansion (3-4 days)
- Runner factory: select executor by agent_type
- Claude CLI executor (DONE — `runner/claude.py`)
- Codex CLI executor
- Gemini CLI executor
- Generic API agent executor (for Ollama, LM Studio, etc.)
- Config-driven agent definitions
- **Legacy ref:** `wrapper.py` (500+ lines), `wrapper_api.py`, `config.toml` agent definitions
- **Key simplification:** No terminal injection (tmux send-keys) — use MCP tools instead
- **Files:** New runner executors, extend `runner/` module
- **Depends on:** MCP Bridge (agents respond via MCP, not stdout)

---

### Phase 6 — Workflow and Productivity

#### 6.1 Jobs/Task Board (4-5 days)
- Job model: id, title, body, status, channel, assignee, messages[]
- JobStore (JSONL)
- JobService: create, update, assign, close, add_message
- API routes: full CRUD + job messages
- Frontend: jobs panel with status columns
- **Legacy ref:** `jobs.py` (400+ lines), `app.py` job routes
- **Key simplification:** Drop reorder, merge with trigger assignment model, archive instead of delete
- **Files:** New models/job.py, stores/job_store.py, services/job_service.py, routes/jobs.py
- **Depends on:** WebSocket, agent registry

#### 6.2 Message Threading (2-3 days)
- Add `reply_to` field to Message model
- Thread view in chat UI
- Reply action on message toolbar
- Context display above composer
- **Legacy ref:** `reply_to` field on messages in `store.py`, `ReplyContext.tsx`
- **Files:** Extend Message model, frontend components
- **Depends on:** Core chat (done)

#### 6.3 Message Editing + Deletion (2 days)
- PATCH /api/messages/{id} for text editing
- DELETE /api/messages/{id} for removal
- Edit/delete in message toolbar UI
- **Legacy ref:** `app.py` PATCH/DELETE routes
- **Files:** Extend message routes, message_store.update
- **Depends on:** Core chat (done)

#### 6.4 File Attachments (2-3 days)
- POST /api/upload — multipart file upload
- Static file serving for uploads
- Attachment model on messages
- Upload button in composer
- Image display in chat bubbles
- **Legacy ref:** `app.py` upload route, `uploads/` directory, `AttachmentPreview.tsx`
- **Files:** New routes/upload.py, extend Message model
- **Depends on:** Core chat

#### 6.5 Sessions / Modes (3-4 days)
- Simplified session model: mode selection (Review, Debate, Build, Planning)
- Mode applies system prompt + role hints to agent context
- No complex phase progression — manual advance
- 3-4 built-in templates
- **Legacy ref:** `session_engine.py` (400+ lines), `session_store.py` (250+ lines)
- **Key simplification:** Modes are context overlays, not state machines. Drop dissent mandate, output marking, phase auto-trigger
- **Files:** New models/session.py, services/session_service.py, routes/sessions.py
- **Depends on:** Agent registry, MCP bridge

#### 6.6 Export/Import (2 days)
- POST /api/export — download JSONL history for channel
- POST /api/import — upload JSONL to channel
- Modal in UI
- **Legacy ref:** `app.py` export/import routes, `ExportImportModal.tsx`
- **Files:** New routes/export.py, frontend modal
- **Depends on:** Message store

#### 6.7 Summaries / Catch-up (2-3 days)
- Summarize channel activity since last visit
- Agent-generated summaries via MCP
- **Legacy ref:** `summaries.py`, summary message type
- **Files:** New services/summary_service.py
- **Depends on:** MCP bridge, message store

---

### Phase 7 — DuckDome Differentiators

#### 7.1 Arena Mode (5-7 days)
- Agent vs agent task comparison
- Structured challenge flow: define task → agents compete → compare results
- Side-by-side output view
- **Legacy ref:** ABSENT — new feature
- **Files:** New arena module (models, service, routes, frontend)
- **Depends on:** Runner expansion, multiple agents working

#### 7.2 Scoring System (3-4 days)
- Per-agent reliability metrics (response rate, response time, error rate)
- Per-agent performance tracking
- Dashboard view
- **Legacy ref:** ABSENT — new feature
- **Files:** New scoring module
- **Depends on:** Delivery tracking, trigger tracking

#### 7.3 Replay System (2-3 days)
- Inspect past arena battles
- Replay timeline of events
- **Legacy ref:** ABSENT — new feature
- **Files:** New replay module
- **Depends on:** Arena mode

---

### Phase 8 — Hardening

#### 8.1 Rich Composer (3-4 days)
- @mention autocomplete popup
- Slash command menu
- Reply context display
- Attachment preview
- **Legacy ref:** `Composer/` directory (8 components), `MentionMenu.tsx`, `SlashMenu.tsx`
- **Files:** Rebuild composer with mention support
- **Depends on:** Agent registry, threading, attachments

#### 8.2 Virtualized Chat Timeline (2 days)
- react-window for large message histories
- Smooth scrolling to latest
- Date dividers
- **Legacy ref:** `ChatTimeline.tsx` with react-window
- **Files:** Replace ChatShell message list
- **Depends on:** Core chat UI

#### 8.3 Zustand State Management (3-4 days)
- Replace local React state with Zustand stores
- Stores: chat, agents, channels, settings, deliveries
- WebSocket-driven updates
- **Legacy ref:** 14 Zustand stores in `apps/web/src/stores/`
- **Key simplification:** Start with 5-6 stores, not 14
- **Files:** New `apps/web/src/stores/` directory
- **Depends on:** WebSocket client

#### 8.4 Server Configuration (2 days)
- config.toml or equivalent for DuckDome
- Agent definitions, ports, MCP config
- config.local.toml for user overrides
- **Legacy ref:** `config.toml`, `config.local.toml.example`, `config_loader.py`
- **Files:** New config module
- **Depends on:** Agent runner expansion

#### 8.5 Cross-Platform Testing (2-3 days)
- Verify Windows, macOS, Linux
- Path normalization
- Electron packaging
- **Legacy ref:** Windows .bat, macOS .sh, platform detection
- **Files:** Platform-specific fixes
- **Depends on:** All features complete

---

## 5. Dependency Graph

```
Phase 3 (Reliability)
  ├── 3.1 Timeout Detection ← Delivery model (done)
  ├── 3.2 Dismiss/Retry ← Timeout detection
  └── 3.3 UI Delivery Indicators ← Timeout + dismiss/retry

Phase 3.5 (WebSocket) ← Core services (done)
  ├── 3.5.1 Backend WS
  └── 3.5.2 Frontend WS Client ← Backend WS

Phase 4 (Human Control)
  ├── 4.1 Loop Guard ← Message routing (done) + Message type field
  ├── 4.2 Rules ← WebSocket (soft — can use polling initially)
  ├── 4.3 Tool Approvals ← WebSocket (soft — can use polling initially)
  ├── 4.4 Settings ← (standalone)
  └── 4.5 API Authentication ← (standalone, should precede Phase 5)

Phase 5 (MCP) ← Message service + Rules + Agent registry
  ├── 5.1 MCP Bridge Core
  ├── 5.2 MCP Transports ← MCP Core
  ├── 5.3 MCP Diagnostics ← MCP Core
  └── 5.4 Agent Runners ← MCP Bridge

Phase 6 (Workflow)
  ├── 6.1 Jobs ← WebSocket + Agent registry
  ├── 6.2 Threading ← Core chat (done)
  ├── 6.3 Edit/Delete ← Core chat (done)
  ├── 6.4 Attachments ← Core chat (done)
  ├── 6.5 Sessions ← MCP + Agent registry
  ├── 6.6 Export/Import ← Message store (done)
  └── 6.7 Summaries ← MCP Bridge

Phase 7 (Differentiators) ← Runners + Multiple agents
  ├── 7.1 Arena ← Runner expansion
  ├── 7.2 Scoring ← Delivery + Trigger tracking
  └── 7.3 Replay ← Arena

Phase 8 (Hardening) ← All features
```

---

## 6. Files to Reference in agentchattr

When implementing each feature, consult these legacy files:

| Feature | Legacy Files | Lines to Focus |
|---------|-------------|----------------|
| WebSocket | `apps/server/src/app.py` | Lines 95-135 (ConnectionManager), 160-280 (WS handler) |
| Loop guard | `apps/server/src/router.py` | Lines 33-96 (full implementation) |
| Rules | `apps/server/src/rules.py` | All (300+ lines) |
| Jobs | `apps/server/src/jobs.py` | All (400+ lines) |
| Sessions | `apps/server/src/session_engine.py` | All (400+ lines) |
| Tool approvals | `apps/server/src/tool_approvals.py` | All (200+ lines) |
| MCP bridge | `apps/server/src/mcp_bridge.py` | All (1000+ lines) — core logic |
| MCP proxy | `apps/server/src/mcp_proxy.py` | All (300+ lines) |
| Agent wrappers | `apps/server/src/wrapper.py` | All (500+ lines) |
| Composer UI | `apps/web/src/components/composer/` | All files (8 components) |
| Chat UI | `apps/web/src/components/chat/` | All files (18 components) |
| Zustand stores | `apps/web/src/stores/` | All files (14 stores) |
| Config loader | `apps/server/src/config_loader.py` | All (43 lines) |
| Room/repo mgmt | `apps/server/src/room_agent_manager.py` | All (300+ lines) |
| Message store | `apps/server/src/store.py` | All (400+ lines) |
| Summaries | `apps/server/src/summaries.py` | All |
| Archive | `apps/server/src/archive.py` | All |

---

## 7. Architecture Differences Summary

| Aspect | agentchattr | DuckDome |
|--------|------------|----------|
| **Backend structure** | Monolith `app.py` (2300+ lines) | Layered: routes → services → stores |
| **Agent scope** | Global registry | Per-channel instances |
| **Channel model** | Plain string names | First-class typed objects (GENERAL/REPO) |
| **Message IDs** | Monotonic integer + UUID | UUID only |
| **Delivery tracking** | ABSENT | First-class state machine |
| **Trigger system** | File-based queues | JSONL store with dedupe |
| **Frontend framework** | React + TypeScript | React + JavaScript (no TypeScript yet) |
| **State management** | Zustand (14 stores) | Local state (no store library yet) |
| **MCP integration** | FastMCP inline | NOT YET — clean module planned |
| **Config** | TOML with loader | NOT YET — needs config module |
| **Testing** | 1 test file | 18 test files, comprehensive coverage |
| **Data directory** | `./data/` (relative) | `~/.duckdome/data/` (home directory) |
| **Agent notification** | Terminal injection (tmux/Win32) | Subprocess execution (one-shot) |

---

## 8. Recommended Build Sequence

The optimal order considering dependencies, user value, and risk:

1. **Phase 3 completion** — Timeout detection + dismiss/retry + UI indicators
2. **WebSocket** — Critical for real-time UX (blocks Phase 4+)
3. **Loop guard** — Safety requirement for multi-agent routing
4. **Settings** — Standalone, quick win
5. **Rules system** — Core control capability
6. **Tool approvals** — Core control capability
7. **MCP bridge** — Unlocks agent connectivity
8. **MCP transports** — Enables real agents to connect
9. **Agent runner expansion** — Multiple agent support
10. **Message threading** — Quick UX win
11. **Message editing/deletion** — Quick UX win
12. **Jobs/tasks** — Workflow structure
13. **File attachments** — UX completeness
14. **Sessions/modes** — Structured workflows
15. **Zustand state management** — Frontend architecture
16. **Rich composer** — UX polish
17. **Virtualized chat** — Performance
18. **Export/import** — Data portability
19. **Arena mode** — Differentiator
20. **Scoring** — Differentiator
21. **Server config** — Ops quality
22. **Cross-platform hardening** — Release readiness

---

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| MCP bridge is complex (1000+ lines in legacy) | High | High | Rebuild incrementally — start with chat_send + chat_read only |
| WebSocket adds complexity to frontend | Medium | High | Start with 4-5 event types, not 50+ |
| TypeScript migration needed for frontend | Medium | Medium | Can stay JS for now, add TS incrementally |
| Agent runner model differs from legacy | High | Medium | DuckDome uses subprocess, not terminal injection — simpler but different |
| Loop guard state management in multi-channel | Low | Medium | Port proven logic from router.py |
| Session/mode simplification loses value | Medium | Low | Start minimal — add complexity only if users need it |
| Cross-platform path handling | Medium | Medium | Use pathlib consistently, test on Windows + macOS |

---

## 10. Open Questions

### Architecture Questions

1. **TypeScript migration:** Should the frontend be migrated to TypeScript before adding more features? The legacy repo uses TypeScript extensively. Adding TS now prevents accumulating JS technical debt, but slows feature velocity.

2. **WebSocket library choice:** Should DuckDome use FastAPI's built-in WebSocket support, or a library like `socketio`? Legacy uses raw WebSocket. FastAPI's built-in is simpler but lacks rooms/namespaces.

3. **State management timing:** When should Zustand be introduced? Adding it now means every new component uses it from the start. Adding it later means refactoring existing components. The legacy repo has 14 stores — DuckDome should probably start with 5-6.

4. **Data directory location:** DuckDome uses `~/.duckdome/data/` (home dir). Legacy uses `./data/` (relative to project). Should DuckDome support both? What about when running from Electron vs dev mode?

5. **Message ID format:** Legacy uses both monotonic integers (for ordering) and UUIDs (for uniqueness). DuckDome uses UUIDs only. Does the lack of monotonic ordering cause issues for cursor-based reads or WebSocket event ordering?

### Feature Questions

6. **Multi-instance agents:** Legacy supports claude-1, claude-2 via slot naming. DuckDome's channel-scoped model means one agent type per channel. Should we support multiple instances of the same agent type in a channel? How would naming work?

7. **MCP cursor persistence:** Legacy cursors are per-agent, per-channel. DuckDome's delivery model already tracks "seen" state. Should cursors still exist as a separate concept, or can delivery state replace them?

8. **Job vs trigger assignment:** Legacy has separate jobs and trigger systems. DuckDome has triggers. Should jobs use the trigger system for assignment, or stay independent? Merging them could simplify but might conflate concepts.

9. **Session simplification scope:** How simple should "modes" be? Legacy sessions have multi-phase progression with role assignments and dissent mandates. Is a simple mode toggle (switches system prompt) sufficient? Or do users need at least 2-3 phases?

10. **Config format:** Legacy uses TOML. Should DuckDome use TOML, YAML, JSON, or environment variables? TOML is Python-native with tomllib (3.11+). JSON is simpler but no comments.

### Migration Process Questions

11. **Feature parity before Arena?** Should all legacy features be migrated before building DuckDome differentiators (Arena, Scoring)? Or is it acceptable to ship Arena without export/import or sessions?

12. **Frontend architecture:** Legacy has a feature-organized component structure with 18+ chat components, 8 composer components, 8 modals. Should DuckDome replicate this structure or use a flatter organization until complexity demands it?

13. **API compatibility:** Should DuckDome's API be compatible with agentchattr's API shape? Or is a clean break acceptable since MCP tools are the primary agent interface?

14. **Testing strategy for frontend:** Legacy has no frontend tests. Should DuckDome add component tests (React Testing Library) or integration tests (Playwright) as features are added?

15. **Electron packaging:** When should Electron packaging (DMG, EXE, AppImage) be set up? Early (to catch packaging issues) or late (after features stabilize)?

### Operational Questions

16. **Data migration:** Should there be a tool to migrate agentchattr data (messages, rules, jobs) to DuckDome format? Or is a clean start acceptable?

17. **Parallel operation:** Should DuckDome be able to run alongside agentchattr during migration? Different ports would allow this, but MCP config would need updating per-agent.

18. **Agent wrapper compatibility:** Legacy agent wrappers (wrapper.py, wrapper_api.py) use terminal injection. DuckDome uses subprocess execution. During migration, should DuckDome support the legacy wrapper interface for backward compatibility?

### Foundational Questions (Added via Review)

19. **Message type system:** Should DuckDome add a `type` field to the Message model now (before more features are built), or defer until rules/jobs/sessions are implemented? Adding it early avoids a migration of existing stored messages later. **Recommendation: Add now — it is a prerequisite for system messages (loop guard), proposal cards (rules, jobs), and session banners.**

20. **API security:** Should DuckDome implement session token authentication before the MCP bridge (Phase 5)? Without it, any process on the machine can send messages as any user/agent. Legacy has `_install_security_middleware` with token validation on all endpoints. **Recommendation: Add lightweight token auth before MCP bridge.**

21. **`@all` mention support:** Should DuckDome support `@all` / `@both` keywords to mention all registered agents in a channel? The legacy router supports this and it is a common user workflow for broadcasting instructions.

22. **Agent identity complexity:** Legacy has a sophisticated identity system (RuntimeRegistry) with claim flow, family-based matching, rename chains, pending/active states, slot-based naming with auto-rename. DuckDome has a simple AgentInstance model. How much of this complexity is needed? At minimum, the claim flow is important for MCP agent reconnection.

23. **Specialized message renderers:** Legacy has 10 specialized in-chat card components (RuleProposalCard, ToolApprovalCard, JobCreatedCard, DecisionCard, SessionDraftCard, etc.). Should DuckDome plan for an extensible renderer system, or build each card ad-hoc as features are added?

24. **Frontend-backend wiring:** The current ChannelShell.jsx creates local-only messages that never hit the backend API. When should this be wired to the real REST API? Before or after WebSocket? **Recommendation: Wire to REST API immediately — it's a false "DONE" claim until connected.**

25. **Agent routes location:** Agent registration/heartbeat/deregistration routes currently live in `triggers.py`. Should these be extracted to a dedicated `agents.py` route file before Phase 4 adds more agent features (roles, multi-instance)?

---

## 11. Review Addendum: Additional Risks (from code review)

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| No message type field makes future features harder to retrofit | High | High | Add `type` field to Message model before building rules/jobs/sessions |
| No API authentication allows spoofed messages | Medium | High | Add lightweight token auth before MCP bridge |
| Frontend mock data creates false "DONE" confidence | High | Medium | Wire frontend to real backend APIs before declaring chat DONE |
| UI component count underestimation (80+ vs 8 built) leads to schedule overrun | High | Medium | Audit legacy components and create realistic UI migration scope |
| Agent identity model is too simple for multi-agent coordination | Medium | Medium | Study legacy RuntimeRegistry claim/rename flow before MCP phase |
| Legacy `wrapper_unix.py` / `wrapper_windows.py` platform-specific injection superseded by subprocess model | Low | Low | Explicitly note as "superseded" — no port needed |
