🧾 1. DuckDome Feature Matrix (Clean + Actionable)

Use this as your source of truth for the rewrite.

🧠 Core System (Non-Negotiable)
Feature	Decision	DuckDome Version	Priority
Mention-based routing	✅ Keep	Deterministic routing + delivery tracking	P0
Loop guard	✅ Keep	Visible loop detection + override	P0
Agent identity + registration	✅ Keep	Clean agent registry UI + status	P0
Presence / heartbeat	✅ Keep	Surface in UI + health dashboard	P0
Multi-channel chat	✅ Keep	Simplified channel UX	P0
Message persistence	✅ Keep	Reliable + replayable timeline	P0
🔥 Reliability Layer (NEW — Critical)
Feature	Decision	DuckDome Version	Priority
Message delivery tracking	🆕 Add	sent → delivered → acknowledged	P0
Missed message detection	🆕 Add	flag ignored @mentions	P0
Retry/escalation system	🆕 Add	resend or reassign tasks	P0
Agent inbox / assignment	🆕 Add	explicit task ownership	P0
Execution timeline	🆕 Add	full trace of events	P0

👉 This is your biggest upgrade over the old repo.

🧠 Control Layer (Human Authority)
Feature	Decision	DuckDome Version	Priority
Tool approvals	✅ Keep	Base system preserved	P0
Tool permission matrix	🆕 Add	per agent + per tool control UI	P0
Rules system	✅ Simplify	reduce complexity, keep power	P0
Sessions/templates	✅ Simplify	turn into “modes” (Review, Debate, Build)	P1
Jobs/tasks	✅ Simplify	merge with inbox/assignment system	P0
🔌 MCP + Tooling Layer
Feature	Decision	DuckDome Version	Priority
MCP bridge	✅ Keep	cleaner abstraction	P0
MCP proxy identity	✅ Keep	preserve security model	P0
MCP tools	✅ Keep	same core tools	P0
MCP installer	🆕 Add	guided setup + auto-fix	P0
MCP diagnostics	🆕 Add	health + validation UI	P0
🏗️ Agent Runtime System
Feature	Decision	DuckDome Version	Priority
CLI wrappers	⚠️ Simplify	reduce duplication, unify logic	P1
API agents	✅ Keep	cleaner config + onboarding	P1
Multi-instance agents	✅ Keep	but simplify UX	P1
Re-registration logic	✅ Keep	but make visible in UI	P1
🧾 Persistence + Data
Feature	Decision	DuckDome Version	Priority
JSONL message store	✅ Keep	same model	P0
Export/import	✅ Keep	cleaner UI flow	P1
State persistence	✅ Keep	centralize config location	P0
Archive system	✅ Keep	optional UI access	P2
🖥️ UI / UX Layer
Feature	Decision	DuckDome Version	Priority
Dual frontend (legacy + React)	❌ Drop	React only	P0
Chat UI	✅ Keep	simplified + structured	P0
Composer UX	✅ Keep	keep mentions + commands	P1
Attachments/images	✅ Keep	basic support	P1
Notification indicators	⚠️ Simplify	keep minimal	P2
Voice input	❓ Optional	defer	P3
🖥️ Electron / App Layer
Feature	Decision	DuckDome Version	Priority
Electron shell	✅ Keep	primary runtime	P0
Backend auto-start	✅ Keep	MUST be owned by Electron	P0
Tray + notifications	⚠️ Simplify	add later	P2
Compatibility checks	❌ Drop	unnecessary early	P3
🚀 Dev / Workflow System (Your Idea)
Feature	Decision	DuckDome Version	Priority
Agent coding workflow	🆕 Add	structured PR pipeline	P1
CodeRabbit integration	🆕 Add	required review gate	P0
One-feature-per-branch	🆕 Add	enforced by agents	P0
PR validation loop	🆕 Add	fix → review → fix cycle	P0
🥊 DuckDome Differentiators
Feature	Decision	DuckDome Version	Priority
Arena mode	🆕 Add	agent vs agent tasks	P1
Scoring system	🆕 Add	reliability + performance	P1
Comparison view	🆕 Add	side-by-side outputs	P1
Replay system	🆕 Add	inspect past battles	P1
Fun modes (roasts, etc.)	⚠️ Optional	plug-in style	P3
🧹 Things to Remove Completely
Feature	Reason
OS launcher explosion	unnecessary complexity
Root wrapper scripts	confusing entrypoints
Dual UI system	major source of confusion
Legacy compatibility layers	not needed in rewrite
Overlapping template storage	redundant