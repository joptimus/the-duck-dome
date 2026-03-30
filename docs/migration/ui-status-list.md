# DuckDome Migration PR Status Tracker (Frontend/UI)

| PR | Title | Status | Branch | Notes |
|----|-------|--------|--------|-------|
| #UI-1 | Design tokens (colors, fonts, animations) | Merged | feature/ui-design-tokens | |
| #UI-2 | SVG icon system (30 icons, agent logos) | Merged | feature/ui-icons | |
| #UI-3 | Shared UI primitives (Dot, Waveform, StatusTag) | Merged | feature/ui-primitives | |
| #UI-4 | Background effects (particles, pulse, orbs) | Merged | feature/ui-effects | |
| #UI-5 | App shell layout (3-zone flex) | Merged | feature/ui-app-shell | |
| #UI-6 | Sidebar (logo, channels, repos, footer) | In Progress | ui/sidebar | @claude implementing |
| #UI-7 | Top Bar (agent status, toolbar buttons) | In Progress | ui/topbar | @codex implementing |
| #UI-8a | Core Message (bubbles, toolbar, roles) | Merged | feature/ui-message-bubble | |
| #UI-8b | System Messages (join, leave, error, divider) | In Progress | ui/system-messages | @claude implementing |
| #UI-8c | Tool Approvals (cards, policy dropdown) | In Progress | ui/tool-approval | @claude implementing |
| #UI-9 | Chat Timeline (virtualization, type dispatch) | Not Started | ui/chat-timeline | @claude next (after 8b/8c) |
| #UI-10 | Composer (slash menu, @mentions) | Merged | feature/ui-composer | |
| #UI-11 | Activity Panel (collapsed, log view) | In Progress | ui/activity-panel | @codex implementing |
| #UI-12 | Agents Panel (process management) | In Progress | ui/agents-panel | @codex implementing |
| #UI-13 | Jobs, Rules & Settings Panels | In Progress | ui/right-panels | @codex implementing |
| #UI-14 | Modals (session launcher, schedule) | Merged | feature/ui-modals | |
| #UI-15 | Integration & Cleanup | Not Started | | @codex next |

**Note:** Phase 3 task split finalized (Message #540). UI-6, UI-8b, UI-8c (@claude) and UI-7, UI-11, UI-12, UI-13 (@codex) in parallel. UI-9 follows 8b/8c.
