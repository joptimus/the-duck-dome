# DuckDome

A local-first desktop app for coordinating multiple AI agents (Claude, Codex, Gemini) in a single workspace. Built for solo developers who want visibility and control over what their agents are doing.

DuckDome gives you channels where you can mention agents, track whether they responded, manage permissions, and compare results — all persisted locally.

> **Status:** Active development. Core chat, agent runtime, and reliability tracking are working. See [Roadmap](#roadmap) for what's next.

## Features

- **Multi-agent chat** — Talk to Claude, Codex, and Gemini in shared channels using `@mentions`
- **Channel-scoped agents** — Bind agents to channels, optionally linked to a local repo
- **Trigger system** — Mentions create trackable triggers that agents claim and execute
- **Delivery tracking** — Every directed message has a state: `sent` → `seen` → `responded` → `resolved` or `timeout`
- **Claude runner** — One-shot CLI execution via `claude --print`, with bounded context and repo-aware working directory
- **Local persistence** — JSONL-based storage in `~/.duckdome/data/`, survives restarts
- **Loop guard** — Detects and prevents infinite agent-to-agent mention chains

### Planned

- Tool approvals and permission matrix
- MCP bridge and diagnostics
- Arena mode (agent vs agent comparison with scoring)
- Session templates and workflow tools
- Export/import

## Architecture

```
the-duck-dome/
├── apps/
│   ├── web/          React UI (Vite)
│   └── desktop/      Electron shell
├── backend/          Python API (FastAPI)
│   └── src/duckdome/
│       ├── models/   Pydantic data types
│       ├── stores/   JSONL persistence
│       ├── services/ Business logic
│       ├── runner/   Agent execution (Claude CLI)
│       └── routes/   REST endpoints
├── docs/             Plans and design docs
└── scripts/          Dev tooling
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

### 2. Install dependencies

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Web
cd ../apps/web
npm install

# Desktop
cd ../desktop
npm install
```

### 3. Run the dev environment

The quickest way to start both backend and web:

```bash
./scripts/dev.sh
```

This starts:
- **Backend** at `http://localhost:8000`
- **Web UI** at `http://localhost:5173`

To also run the Electron shell:

```bash
cd apps/desktop
npm run dev
```

### 4. Run tests

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
| `POST` | `/api/runners/execute` | Execute next pending trigger |

## Roadmap

DuckDome is being rebuilt from a legacy project ([agentchattr](https://github.com/joptimus/agentchattr)) with a focus on reliability and clean architecture.

| Phase | Goal | Status |
|-------|------|--------|
| 0 | Foundation and guardrails | Done |
| 1 | Legacy discovery and feature lock | Done |
| 2 | Core runtime spine | Done |
| 3 | Reliability layer | In progress |
| 4 | Human control layer | Planned |
| 5 | MCP and agent management | Planned |
| 6 | Workflow and productivity | Planned |
| 7 | Arena mode and differentiators | Planned |
| 8 | Hardening and cleanup | Planned |

See [`docs/milestone-plan.md`](docs/milestone-plan.md) for details.

## Contributing

This is a solo-developer project. If you're interested in contributing, open an issue first to discuss.

All PRs go through [CodeRabbit](https://coderabbit.ai/) automated review.

## License

TBD
