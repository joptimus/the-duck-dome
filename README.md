# DuckDome

A local-first desktop app for coordinating multiple AI agents (Claude, Codex, Gemini) in a single workspace. Built for solo developers who want visibility and control over what their agents are doing.

DuckDome gives you channels where you can mention agents, track whether they responded, manage permissions, and compare results — all persisted locally.

> **Status:** Core feature-complete. Backend and UI migration from [agentchattr](https://github.com/joptimus/agentchattr) are done. All agent coordination, MCP tooling, tool approvals, and the full design-system UI are running on main.

## Features

- **Multi-agent chat** — Talk to Claude, Codex, and Gemini in shared channels using `@mentions` with autocomplete
- **Channel-scoped agents** — Bind agents to channels, optionally linked to a local repo
- **Trigger system** — Mentions create trackable triggers that agents claim and execute
- **Delivery tracking** — Every directed message has a state: `sent` → `seen` → `responded` → `resolved` or `timeout`
- **Tool approvals** — Approve or deny agent tool calls inline in chat, with per-tool auto-approve policies
- **MCP bridge** — Full MCP HTTP transport (port 8200) exposing `chat_send`, `chat_read`, `chat_join`, `chat_rules`, and more
- **Jobs system** — Scheduled and one-shot jobs with a dedicated panel UI
- **Rules system** — Channel-level rules reviewable and approvable from the UI
- **Composer** — Rich message input with slash commands and `@mention` popups
- **Session launcher** — Start coordinated multi-agent sessions from the UI
- **Agent management panel** — Start, stop, add, and remove channel-bound agents
- **Activity, agents, jobs, rules, and settings panels** — Full right-panel suite accessible from the top bar
- **Claude runner** — One-shot CLI execution via `claude --print`, with bounded context and repo-aware working directory
- **Local persistence** — JSONL-based storage in `~/.duckdome/data/`, survives restarts
- **Loop guard** — Detects and prevents infinite agent-to-agent mention chains

### Planned

- Arena mode (agent vs agent comparison with scoring)
- Export/import

## Architecture

```text
the-duck-dome/
├── apps/
│   ├── web/                    React UI (Vite)
│   │   └── src/
│   │       ├── components/     Design system components
│   │       │   ├── chat/       ChatTimeline, Composer, MessageBubble, ToolApprovalCard, …
│   │       │   ├── layout/     AppShell
│   │       │   ├── sidebar/    Sidebar, ChannelList, RepoList
│   │       │   ├── topbar/     TopBar, PendingApprovalPill
│   │       │   ├── panels/     ActivityPanel, AgentsPanel, JobsPanel, RulesPanel, SettingsPanel, RightPanel
│   │       │   ├── modals/     SessionLauncher, ScheduleModal
│   │       │   ├── effects/    ParticleField, ElectricPulse, AmbientOrbs
│   │       │   ├── icons/      30+ SVG icon exports
│   │       │   └── primitives/ Dot, Waveform, SectionLabel, ToolbarBtn, …
│   │       ├── features/
│   │       │   └── channel-shell/  ChannelShell (data layer: state, WebSocket, API)
│   │       ├── tokens/         CSS custom properties (colors, typography, animations)
│   │       └── constants/      agents.js, composer.js
│   └── desktop/                Electron shell
├── backend/                    Python API (FastAPI, port 8000)
│   └── src/duckdome/
│       ├── models/             Pydantic data types
│       ├── stores/             JSONL persistence (~/.duckdome/data/)
│       ├── services/           Business logic
│       ├── runner/             Agent execution (Claude/Codex/Gemini CLI)
│       ├── mcp/                MCP HTTP transport (port 8200) + bridge
│       └── routes/             REST + WebSocket endpoints
├── docs/                       Plans and design docs
└── scripts/                    Dev tooling
```

**Layer rules:**
- `web` — UI only, no business logic
- `desktop` — App lifecycle only, no business logic
- `backend` — Routes → Services → Stores, strict boundaries

## Prerequisites

- Python 3.11+
- Node.js 18+
- npm

For the Claude runner to work, you also need:
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated

## Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/joptimus/the-duck-dome.git
cd the-duck-dome
```

### 2. Run the dev environment

The dev script installs dependencies automatically on first run and starts the backend, web UI, and Electron shell.

**macOS / Linux:**

```bash
./scripts/dev.sh
```

**Windows (PowerShell):**

```powershell
.\scripts\dev.ps1
```

> If you get an execution policy error, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` first.

This starts:
- **Backend** at `http://localhost:8000`
- **MCP transport** at `http://localhost:8200`
- **Web UI** at `http://localhost:5173`
- **Electron** shell

The Windows script automatically kills stale processes on ports 8000, 8200, and 5173 before starting.

### 3. Run tests

```bash
cd backend
python -m pytest
```

## API

The backend exposes a REST API at `http://localhost:8000`. Key endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/channels` | List channels |
| `POST` | `/api/channels` | Create a channel |
| `GET` | `/api/channels/{id}/messages` | List messages in a channel |
| `POST` | `/api/channels/{id}/messages` | Send a message |
| `GET` | `/api/channels/{id}/agents` | List channel-bound agents |
| `GET` | `/api/channels/{id}/triggers` | List triggers for a channel |
| `POST` | `/api/runners/execute` | Execute next pending trigger |
| `GET` | `/api/jobs` | List scheduled jobs |
| `POST` | `/api/jobs` | Create a job |
| `GET` | `/api/rules` | List channel rules |
| `POST` | `/api/tool-approvals` | Submit a tool approval decision |
| `WS` | `/ws` | WebSocket for real-time events |
| MCP | `http://localhost:8200` | MCP HTTP transport for agent tooling |

## Roadmap

DuckDome was rebuilt from [agentchattr](https://github.com/joptimus/agentchattr) with a focus on reliability and clean architecture. The migration is complete.

| Area | Status |
|------|--------|
| Backend — core runtime, WebSocket, persistence | Done |
| Backend — MCP bridge and HTTP transport | Done |
| Backend — tool approvals, rules, jobs system | Done |
| Backend — multi-runner (Claude, Codex, Gemini) | Done |
| UI — design system (tokens, icons, effects, primitives) | Done |
| UI — layout, sidebar, top bar, composer | Done |
| UI — chat timeline, message types, tool approval cards | Done |
| UI — all panels (activity, agents, jobs, rules, settings) | Done |
| UI — modals (session launcher, scheduler) | Done |
| Arena mode (agent vs agent comparison with scoring) | Planned |
| Export/import | Planned |

## Contributing

This is a solo-developer project. If you're interested in contributing, open an issue first to discuss.

All PRs go through [CodeRabbit](https://coderabbit.ai/) automated review.

## License

TBD
