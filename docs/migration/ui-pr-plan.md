# DuckDome UI PR Plan

> **Date:** 2026-03-29
> **Baseline:** After backend migration PRs merge
> **Design source of truth:** `agentchattr/desktop/docs/the-duckdome.jsx`
> **Design spec reference:** `docs/duckdome-design-spec.md`
> **Current state:** Minimal channel-shell with flat CSS, plain message cards, basic sidebar, no design tokens, no icons, no panels, no modals, no effects.
> **Path convention:** All new files under `apps/web/src/` (monorepo web app root)

---

## Gap Analysis: Current vs. Design

| Area | Current | Design Target |
|------|---------|---------------|
| **Design tokens** | Hardcoded hex values in flat CSS | CSS custom properties: surfaces, text, brand, status, 8 agent color sets (primary/bg/border), typography vars, 16 keyframe animations |
| **Typography** | System font (Inter) | Orbitron (display), Rajdhani (labels), Source Sans 3 (body), JetBrains Mono (code). Font scale: body 16px, labels 14-15px, small 12px, timestamps 11px, display 20-22px |
| **Icons** | None (text only, some emojis) | 30 named SVG icon components + BoltIcon (separate, with optional glow filter) + 7 agent logo SVGs + fallback |
| **Layout** | 2-column grid (sidebar + main), no panels | 3-zone flex: sidebar (228px) + main + slide-in right panel |
| **Sidebar** | Channel list only, no logo, no repos, no user footer | Logo header w/ gradient text + breathe animation, pinned drawer, channels w/ unread badge gradients + active left bar, repos list, user footer w/ session launcher |
| **Top bar** | Basic channel header card | 50px bar with BoltIcon, waveform, agent status strip (AgentLogo SVGs + overlaid status dots), toolbar buttons (including Agents button), electric pulse |
| **Messages** | Flat cards, no avatars, no hover actions | Agent-colored bubbles with avatar rings, hover border brightening (22% -> 40%), margin expansion (18px -> 32px), floating toolbar, role dropdown (11 roles, no emojis), @mention highlighting |
| **Composer** | Simple input + button | 14 slash commands, @mention popup with @all row + keyboard index offsetting, purple border state when popup open, voice/schedule buttons, gradient send button with shimmer |
| **Panels** | RuntimeDetailsPanel (table) | Activity (380px), Agents (360px), Jobs (380px), Rules (380px), Settings (380px) panels |
| **Modals** | ChannelCreateModal only | Session Launcher (4 types with roles), Schedule Modal, generic Modal wrapper with overlay + card specs |
| **Effects** | Single pulse keyframe | ParticleField (45 particles, 4 colors), ElectricPulse (vertical + horizontal modes), ambient orbs, 16 keyframe animations |
| **System messages** | Same card style as chat | Join/leave compact lines, error bars, info lines, date dividers |
| **Tool approvals** | Not rendered | Inline approval cards with approve/deny/policy UI |
| **Thinking indicator** | "Claude is working..." text | Multi-agent thinking strip with colored dots |

---

## Shared Constants

### `allAgentTypes`

A shared constant array used across multiple components (AgentsPanel add-agent flow, @mention popup, agent status strip):

```js
const allAgentTypes = ["claude", "codex", "gemini", "kimi", "qwen", "kilo", "minimax"];
```

File: `apps/web/src/constants/agents.js`

This constant and the `agentMeta` map (8 entries including "user") should be exported from a single shared location and imported wherever needed.

---

## PR #UI-1: Design System Tokens & Global CSS

### Goal
Replace hardcoded CSS values with a design token system. All subsequent UI PRs reference these tokens.

### Scope
- `apps/web/src/tokens/colors.css` — All CSS custom properties:

  **Surfaces:** `--bg-app: #0D1117`, `--bg-surface: #111827`, `--bg-elevated: #1A2233`, `--bg-sidebar: #0B1020`, `--bg-input: #0F172A`

  **Text:** `--text-primary: #E6EDF3`, `--text-secondary: #9CA3AF`, `--text-muted: #6B7280`, `--text-bright: #F8FAFC`

  **Brand:** `--blue: #00D4FF`, `--purple: #A855F7`, `--purple-glow: #C084FC`, `--gradient: linear-gradient(90deg, #00D4FF 0%, #A855F7 100%)`

  **Status:** `--success: #00FFA3`, `--warning: #F59E0B`, `--error: #FF4D6D`, `--info: #38BDF8`

  **Status color mapping (CSS vars):**
  - `--status-processing: var(--blue)` (#00D4FF)
  - `--status-attacking: var(--error)` (#FF4D6D) + warningFlash animation + BoltIcon
  - `--status-debating: var(--purple)` (#A855F7)
  - `--status-analyzing: var(--info)` (#38BDF8)
  - `--status-idle: var(--text-muted)` (#6B7280)

  **Border:** `--border: #1F2937`

  **Agent colors (8 entries with primary/bg/border variants):**
  | Agent   | Primary   | bg                          | border                      |
  |---------|-----------|-----------------------------|-----------------------------|
  | Claude  | #FF8A5C   | rgba(255,138,92, 0.06)      | rgba(255,138,92, 0.22)      |
  | Codex   | #00FFAA   | rgba(0,255,170, 0.06)       | rgba(0,255,170, 0.22)       |
  | Gemini  | #6BAAFF   | rgba(107,170,255, 0.06)     | rgba(107,170,255, 0.22)     |
  | Kimi    | #3D9EFF   | rgba(61,158,255, 0.06)      | rgba(61,158,255, 0.22)      |
  | Qwen    | #A78BFF   | rgba(167,139,255, 0.06)     | rgba(167,139,255, 0.22)     |
  | Kilo    | #EEFF41   | rgba(238,255,65, **0.05**)  | rgba(238,255,65, **0.18**)  |
  | MiniMax | #3DFFC8   | rgba(61,255,200, 0.06)      | rgba(61,255,200, 0.22)      |
  | User    | #A855F7   | rgba(168,85,247, 0.06)      | rgba(168,85,247, 0.22)      |

  Note: Kilo uses 5%/18% (not 6%/22%) because pure yellow is visually louder.

- `apps/web/src/tokens/typography.css` — Google Fonts import for Orbitron, Rajdhani, Source Sans 3, JetBrains Mono. Font family vars and scale:

  **Font families:**
  - `--font-display: 'Orbitron'` — Headers, logo, send button, panel titles
  - `--font-label: 'Rajdhani'` — Labels, tags, status badges, section headers
  - `--font-body: 'Source Sans 3'` — Body text, descriptions, inputs
  - `--font-mono: 'JetBrains Mono'` — Code, timestamps, file paths, terminal output

  **Font scale (exact sizes):**
  - 22px — Modal headers, close buttons (Orbitron 700)
  - 20px — Panel section headers (Orbitron 700)
  - 18px — Session type names, large labels (Rajdhani 700)
  - 16px — Body text, message content, inputs, descriptions (Source Sans 3 400-500)
  - 15px — Labels, detail text, agent names in panels (Source Sans 3 500 / Rajdhani 700)
  - 14px — Code tags, channel names, mono text (JetBrains Mono 400-500)
  - 13px — Helper text, secondary labels (Source Sans 3 400)
  - 12px — Status tags, section labels, small UI elements (Rajdhani 700)
  - 11px — Timestamps (JetBrains Mono 400, often at 50% opacity)
  - 10px — Micro labels (rare)

  **Letter-spacing tokens (6 values):**
  - `--ls-section: 0.14em` — Section labels (CHANNELS, REPOS, COMMANDS)
  - `--ls-status: 0.10em` — Status tags (PROCESSING, APPROVED), policy headers
  - `--ls-changes: 0.08em` — Changes label
  - `--ls-panel: 0.06em` — Panel titles (ACTIVITY, AGENTS), send button, agent names
  - `--ls-bubble: 0.04em` — Agent names in bubbles, sidebar items
  - `--ls-logo: 0.15em` — Logo subtitle

- `apps/web/src/tokens/animations.css` — All 16 keyframe animations:
  1. `pulse` — Opacity 0.5 -> 1 -> 0.5, 1.5s. Used: dots, unread badges, pending pill
  2. `breathe` — Box-shadow intensity oscillation, 3s. Used: logo container
  3. `shimmer` — Background-position -200% -> 200%, 2s. Used: send/apply buttons
  4. `fadeUp` — Opacity 0->1, translateY 8px->0, 0.3s. Used: all message entries
  5. `slideIn` — TranslateX 100%->0, opacity 0->1, 0.25s. Used: right panels
  6. `barPulse` — ScaleY 0.2 -> 1 -> 0.2. Used: waveform bars
  7. `borderGlow` — Border-color cycles blue->purple, 6s. Used: agent strip
  8. `textPulse` — Filter brightness 1 -> 1.5 -> 1. Used: thinking text
  9. `voltFlash` — Quick opacity flickers, 1s. Used: logo text
  10. `orbFloat` — Gentle translate + scale drift, continuous. Used: ambient orbs
  11. `warningFlash` — Opacity 1 -> 0.4 -> 1, 1s. Used: ATTACKING status
  12. `shakeSubtle` — 0.5px translate jitter. Used: error states
  13. `glitchX` — TranslateX jitter. Used: glitch effects
  14. `pulseTravelDown` — Top -40px -> calc(100%+40px). Used: vertical electric pulse
  15. `pulseTravelRight` — Left -60px -> calc(100%+60px). Used: horizontal electric pulse
  16. `modalIn` — Scale 0.95->1, translateY 10px->0, opacity 0->1, 0.25s. Used: modals

- `apps/web/src/tokens/index.css` — Imports all token files, box-sizing reset, scrollbar styles (5px width, transparent track, #1F2937 thumb, 3px border-radius)
- `apps/web/src/index.css` — Refactor to import tokens, remove hardcoded values

### Depends On
None (foundation PR)

### Verification
- All CSS custom properties resolve in browser DevTools
- Fonts load (check Network tab)
- No visual regressions
- `npm run build` succeeds

---

## PR #UI-2: SVG Icon System

### Goal
Create reusable SVG icon library and agent logo components.

### Scope
- `apps/web/src/components/icons/Icons.jsx` — **30 named icon components** organized by category:

  | Category   | Icons |
  |------------|-------|
  | ACTIONS    | Reply, Pin, Copy, Check, Trash, Edit |
  | PANELS     | Jobs, Rules, Gear, Terminal, Users |
  | MEDIA      | Mic, Clock, Help, Play, Pause |
  | NAV        | Chevron (with rotation prop), Folder, Cube, Refresh, Plus, Shuffle |
  | APPROVAL   | Shield, ShieldCheck, ShieldX, Eye, X |
  | SYSTEM     | Power, Stop |

  All icons take `{size, color}` props. Default color is `currentColor`.

- `apps/web/src/components/icons/BoltIcon.jsx` — **Separate component** with optional glow filter (`feGaussianBlur stdDeviation 2`). Takes `{size, color, glow}` props. When glow=true, renders a blurred background copy at 30% opacity behind the main path.

- `apps/web/src/components/icons/AgentLogo.jsx` — 7 agent-specific SVG brand marks + fallback:

  | Agent   | Description |
  |---------|-------------|
  | Claude  | 4 rotated lines (0/45/90/135 deg) radiating from center + 2.5r filled circle |
  | Codex   | Hexagon outline (stroke 1.8) + 3r filled circle center (0.8 opacity) |
  | Gemini  | 4-point sparkle (4 teardrop paths) + 2r center dot |
  | Kimi    | Overlapping moon crescent (filled, 0.9 opacity) + 7r circle outline (stroke 1.8) |
  | Qwen    | Concentric circles (8r + 4r outlines) + 1.5r center dot + 4 crosshair lines |
  | Kilo    | Angle brackets (< >) stroke 2.2 + diagonal slash (0.7 opacity) |
  | MiniMax | Sine wave path (stroke 2) + 2r center dot |
  | Fallback | First letter of agent name in Orbitron 700 14px |

  Each takes `{agent, size}`. Reads color from `agentMeta[agent].color`.

### Depends On
PR #UI-1

### Verification
- Each icon renders with correct SVG paths
- AgentLogo renders correct mark per agent type
- BoltIcon glow filter renders correctly when enabled
- Icons inherit color via `currentColor`

---

## PR #UI-3: Shared UI Primitives

### Goal
Build small reusable components used across panels and areas.

### Scope
- `apps/web/src/components/shared/Dot.jsx` — Pulsing colored dot
  - Size: configurable, default 8px
  - Border-radius: 50%, box-shadow: `0 0 6px {color}, 0 0 14px {color}60`
  - Animation: `pulse 1.5s ease-in-out infinite`

- `apps/web/src/components/shared/Waveform.jsx` — Animated bar visualizer
  - 16 bars (configurable), 2px wide, gap 1.5px, height container 18px
  - Each bar: border-radius 1px, color at 70% opacity
  - Animation: `barPulse` with random duration (0.3-0.8s) and staggered delay (i*0.04s)

- `apps/web/src/components/shared/SectionLabel.jsx` — Uppercase label with dot prefix
  - Font: Rajdhani 700, 14px, letter-spacing 0.14em, uppercase
  - Prefix dot: 4px circle, box-shadow glow at 8px/16px
  - Text-shadow: `0 0 8px {color}50`

- `apps/web/src/components/shared/ToolbarBtn.jsx` — 32x32 icon button
  - Border-radius: 7px
  - Default: transparent bg, transparent border, text-muted color
  - Hover: `rgba(255,255,255,0.03)` bg, border-color border, text-primary color
  - Active: blue bg at 18%, 1px solid blue at 60%, blue color, box-shadow `0 0 12px blue35, 0 0 28px blue16`
  - Transition: all 0.12s

- `apps/web/src/components/shared/CodeTag.jsx` — Inline code pill
  - Background: blue at 12%, border: 1px solid blue at 22%, border-radius: 4px
  - Padding: 1px 6px, font: JetBrains Mono 14px, blue color

- `apps/web/src/components/shared/StatusTag.jsx` — Agent status badge
  - Font: Rajdhani 700, 12px, letter-spacing 0.1em
  - Padding: 2px 8px, border-radius: 4px
  - Background: status-color at 12%, border: 1px solid status-color at 25%
  - ATTACKING variant: adds BoltIcon (12px) and `warningFlash 1s ease infinite`

- `apps/web/src/components/shared/RoleTag.jsx` — Purple role label pill
  - Font: JetBrains Mono 12px
  - Padding: 2px 8px, border-radius: 4px
  - Background: purple at 15%, border: 1px solid purple at 30%, color: purple-glow

- `apps/web/src/constants/agents.js` — Shared `allAgentTypes` array and `agentMeta` map (8 entries)

### Depends On
PR #UI-1, PR #UI-2

### Verification
- Each component renders in isolation
- StatusTag shows correct color per status value
- StatusTag ATTACKING variant shows BoltIcon and flashes

---

## PR #UI-4: Background Effects

### Goal
Add decorative particle field, electric pulse, and ambient gradient orbs.

### Scope
- `apps/web/src/components/effects/ParticleField.jsx` — Canvas-based particle system
  - **45 particles** exactly
  - **4 colors:** blue (#00D4FF), purple (#A855F7), purpleGlow (#C084FC), success (#00FFA3)
  - **Velocity ranges:** vx: (random-0.5)*0.35, vy: (random-0.5)*0.2
  - Size: random*2+0.5, alpha: random*0.3+0.05
  - Phase oscillation: ps = 0.008+random*0.012
  - Glow effect: secondary arc at 3.5x size, 7% of particle alpha
  - Canvas: absolute inset, pointer-events none, z-index 0
  - Cleanup: cancelAnimationFrame on unmount, removeEventListener for resize

- `apps/web/src/components/effects/ElectricPulse.jsx` — CSS lightning pulse along edges
  - **Two modes:** vertical (right edge, 3px wide, 40px tall pulse) and horizontal (bottom edge, 3px tall, 60px wide pulse)
  - Props: `{vertical=true, color, minDelay, maxDelay}`
  - Random interval fires between minDelay-maxDelay ms
  - Pulse duration: 0.8+random*0.8s
  - Uses `pulseTravelDown` (vertical) or `pulseTravelRight` (horizontal) keyframes
  - Radial gradient with box-shadow glow

- `apps/web/src/components/effects/AmbientOrbs.jsx` — Two radial gradients (blue + purple)
  - Blue orb: top -150px, left 20%, 700x700px, blue at 0A opacity, `orbFloat 20s`
  - Purple orb: bottom -200px, right 10%, 800x800px, purple at 08 opacity, `orbFloat 25s reverse`
  - Both: pointer-events none, z-index 0

### Depends On
PR #UI-1

### Verification
- Particles animate smoothly, clean up on unmount
- ElectricPulse fires at random intervals in both vertical and horizontal modes
- All effects have `pointer-events: none`

---

## PR #UI-5: App Shell Layout

### Goal
Replace 2-column grid with 3-zone flex layout: sidebar + main + optional right panel.

### Scope
- `apps/web/src/components/layout/AppShell.jsx` — Root layout with three zones
  - Full viewport, flex row, overflow hidden, background: bg-app
  - Sidebar zone: 228px, min-width 228px
  - Main content zone: flex 1, flex-column, min-width 0, z-index 2
  - Right panel slot: flex-shrink 0 (panels declare their own width), slides in with `slideIn 0.25s ease`
- `apps/web/src/App.jsx` — Refactor to use AppShell
- Wire ParticleField and AmbientOrbs as background layers

### Depends On
PR #UI-4

### Verification
- Three-zone layout renders correctly
- Right panel slides in/out with animation
- Background effects visible behind content

---

## PR #UI-6: Sidebar

### Goal
Full design sidebar: logo header, pinned drawer, channels with unread badges, repos list, user footer.

### Scope
- `apps/web/src/components/sidebar/Sidebar.jsx` — Full sidebar with 5 zones
  - Width: 228px, min-width: 228px
  - Background: bg-sidebar at F0 opacity, backdrop-filter: blur(12px)
  - Border-right: 1px solid border
  - Flex column, full height, z-index: 2

  **Logo header:**
  - Container: 32x32px, border-radius: 8px, gradient bg (blue30 -> purple30), border 1.5px solid blue50
  - Box-shadow: `0 0 16px blue35, 0 0 32px purple20`
  - Animation: `breathe 3s ease-in-out infinite`
  - Title: "THE DUCKDOME" — Orbitron 800, 12px, letter-spacing 0.15em, gradient text (-webkit-background-clip: text), voltFlash animation
  - Subtitle: "AI AGENT BATTLEGROUND" — Rajdhani 600, 10px, letter-spacing 0.14em, purple-glow at 40%
  - Bottom: gradient line (2px, blue->purple, 40% opacity)

  **Pinned drawer:** collapsible section with chevron

- `apps/web/src/components/sidebar/ChannelList.jsx` — Channel rows with active highlight, unread badges
  - Row: padding 6px 14px 6px 16px, flex row, gap 8px
  - Active: bg blue at 0C opacity, **2px gradient left bar** (absolute positioned, top 0, bottom 0, left 0)
  - Hash: JetBrains Mono 15px, blue when active, text-muted when not
  - Name: Source Sans 3 16px, weight 600/bright when active, weight 400/secondary when not
  - Hover delete: x button, visible on hover only
  - **Unread badge:** min-width 18px, height 18px, border-radius 9px, **background: linear-gradient(135deg, purple, error)**, font: Rajdhani 700 12px white, box-shadow: `0 0 10px purple60`, animation: `pulse 1.5s ease-in-out infinite`

- `apps/web/src/components/sidebar/RepoList.jsx` — Repos section with folder icons
  - Header: FolderIcon, PlusIcon, RefreshIcon row, each 15px, 50% opacity
  - Row: padding 5px 14px 5px 16px, CubeIcon (14px, text-muted) + name Source Sans 3 15px text-secondary, text overflow: ellipsis
  - Separator between channels and repos: gradient line (purple30 -> border -> transparent)

- `apps/web/src/components/sidebar/SidebarFooter.jsx` — User avatar + session launcher
  - Padding: 10px 16px, border-top: 1px solid border
  - Avatar: 24x24px circle, gradient bg (blue35->purple30), 1.5px border blue40, Orbitron 700 14px "J" initial
  - Name: Source Sans 3 500, 16px, text-secondary
  - Session button: 26x26px circle, gradient bg, PlayIcon 12px white, box-shadow glow (`0 0 10px blue40, 0 0 20px purple20`)

### Depends On
PR #UI-2, #UI-3, #UI-5

### Verification
- Logo renders with breathing animation and voltFlash text
- Channel selection works with active highlight and gradient left bar
- Unread badges show with gradient background and pulse animation

---

## PR #UI-7: Top Bar

### Goal
Replace ChannelHeader with 50px top bar: BoltIcon, waveform, agent status strip, **Agents button**, toolbar buttons.

### Scope
- `apps/web/src/components/topbar/TopBar.jsx` — Full top bar
  - Height: 50px, flex row, align center, padding: 0 18px, gap: 10px
  - Background: bg-surface at D0 opacity, backdrop-filter: blur(12px)
  - Border-bottom: 1px solid border, flex-shrink: 0, position: relative
  - ElectricPulse on bottom edge (horizontal mode, purple, delay 5-12s)

  **Contents (left to right):**
  1. BoltIcon (16px, blue)
  2. Channel name — Orbitron 600, 16px, text-bright, letter-spacing 0.04em
  3. Waveform (blue, 12 bars)
  4. Flex spacer
  5. **Agent status strip** — clickable row, border-radius 8px, 1px border (blue40 when activity panel open), `borderGlow 6s` animation. Each agent: **AgentLogo SVG (16px)** with **overlaid status dot** (positioned absolute, bottom -1px, right -1px, 5x5px circle, border-radius 50%, green (success) + `0 0 4px success` glow when running, text-muted when stopped, border: 1.5px solid bg-surface as separator gap) + agent name in Source Sans 3 14px
  6. PendingApprovalPill (between agent strip and toolbar)
  7. **Toolbar buttons row** (gap: 3px): Activity (BoltIcon), **Agents (UsersIcon)**, Jobs (JobsIcon), Rules (RulesIcon), Pinned (PinIcon), Settings (GearIcon), Help (HelpIcon)

### Depends On
PR #UI-2, #UI-3, #UI-4, #UI-5

### Verification
- Agent status strip shows all agents with correct AgentLogo SVGs and overlaid status dots
- Agents button is present in toolbar and toggles Agents panel
- Toolbar buttons toggle panel state
- Electric pulse on bottom edge fires in horizontal mode

---

## PR #UI-8a: Core Message Bubble with Hover Actions

### Goal
Agent-colored bubbles with avatar rings, floating toolbar, role dropdown.

### Scope
- `apps/web/src/components/chat/MessageBubble.jsx` — Agent-colored bubble with avatar

  **Agent messages (left-aligned):**
  - Avatar: 30x30px circle, bg agent-color 15%, border 1.5px agent-color 50%, AgentLogo 18px
  - Margin-right: 12px, margin-top: 2px
  - Bubble max-width: 72%, border-radius: 14px 14px 14px 4px (flat corner near avatar)

  **User messages (right-aligned):**
  - No avatar, bubble max-width: 62%, border-radius: 14px 14px 4px 14px

  **Bubble shared:**
  - Background: agent-bg (6% tinted)
  - Border: 1px solid agent-border (22%) — **brightens to 40% on hover**
  - Padding: 12px 16px, position: relative
  - Transition: border-color 0.15s
  - **Margin-bottom: 18px -> 32px on hover** (transition: 0.12s) — makes room for toolbar
  - Entry animation: `fadeUp 0.3s ease {idx*0.06}s both`

  **Header row:** flex, gap 8px, flex-wrap: wrap
  - Agent name: Rajdhani 700, 15px, agent-color, uppercase, letter-spacing 0.04em
  - StatusTag
  - Timestamp: JetBrains Mono, 12px, text-muted
  - **"choose a role" button:** appears on hover only. Padding 2px 8px, border-radius 4px. Default: transparent bg/border/muted. Hover: purple border/text. Open state: purple bg 15%, purple border 60%

  **Body:** Source Sans 3 16px, line-height 1.6, text-primary
  - @mentions split via `/@\w+/` regex -> blue color, blue bg 10%, border-radius 3px, padding 1px 4px, weight 500

  **Details section (optional):**
  - Divider: 1px line, agent-color 18%, margin-bottom 7px
  - Label: "Changes:" — Rajdhani 12px uppercase, letter-spacing 0.08em, agent-color, BoltIcon 12px
  - Items: 4px dot bullet (agent-color, 60% opacity) + Source Sans 3 15px text-secondary
  - Inline code: backtick pattern split -> CodeTag component

- `apps/web/src/components/chat/MessageToolbar.jsx` — Floating action bar
  - Position: absolute, bottom: -16px, right: 12px
  - Background: bg-elevated, border: 1px solid border, border-radius: 6px, padding: 2px
  - Box-shadow: 0 4px 16px rgba(0,0,0,0.5)
  - Opacity/transform transition: 0.12s, pointer-events: none when hidden, z-index: 50
  - **Buttons (28x28px each, border-radius 5px):**
    1. Reply (ReplyIcon 13px)
    2. Pin (PinIcon 13px)
    3. Copy (CopyIcon 13px) -> on click: swaps to CheckIcon, turns success, "Copied!" tooltip (absolute top: -22px, centered, success bg, black text, 12px 600, border-radius 4px, fadeUp 0.2s). Reverts after 1.8s.
    4. Convert to Job (BoltIcon 14px)
    5. 1px vertical divider (height 16px, border color, margin 0 2px)
    6. Delete (TrashIcon 13px) — hover: red bg rgba(255,77,109,0.15), error color

- `apps/web/src/components/chat/RoleDropdown.jsx` — Role picker popup
  - Position: absolute, top: 28px, left: 0, z-index: 120
  - Background: bg-surface, border: 1px solid border, border-radius: 10px
  - Padding: 12px, min-width: 260px
  - Box-shadow: 0 8px 32px rgba(0,0,0,0.6), 0 0 20px blue08
  - **Roles (text only, NO emojis):** None (pre-selected: blue bg 30%, blue border 60%), Planner, Designer, Architect, Builder, Reviewer, Researcher, Red Team, Wry, Unhinged, Hype
  - Pill style: padding 5px 12px, border-radius 16px, bg-elevated, 1px border, Source Sans 3 15px
  - Custom input at bottom: full width, border-radius 8px, bg-input

### Depends On
PR #UI-2, #UI-3

### Verification
- Agent messages render with correct avatar and color tinting
- Hover brightens border from 22% to 40% opacity
- Hover expands margin-bottom from 18px to 32px
- Floating toolbar shows/hides on hover
- Role dropdown opens with 11 roles (no emojis)

---

## PR #UI-8b: System Messages & Date Dividers

### Goal
Distinct rendering for system-level messages: join/leave, errors, info, date dividers.

### Scope
- `apps/web/src/components/chat/SystemMessage.jsx` — Join/leave, error, info variants

  **Join/Leave:** centered line, gap 6px, padding 4px 0
  - Dot 5px (green for join, muted for leave)
  - Agent name: Source Sans 3 15px, agent-color, weight 500
  - Content: Source Sans 3 15px, text-muted
  - Timestamp: JetBrains Mono 11px, text-muted 50%

  **Error:** flex row, gap 10px, padding 8px 14px, margin 6px 0, border-radius 8px
  - Background: warning 6%, border: 1px solid warning 15%
  - Warning triangle SVG (16px, warning color, stroke 2)
  - Text: Source Sans 3 15px text-secondary, agent name in agent-color weight 500
  - Timestamp: JetBrains Mono 11px right-aligned

  **Info:** centered, gap 8px, padding 6px 0
  - BoltIcon 14px info color, no glow
  - Text: Source Sans 3 15px text-secondary
  - Timestamp: JetBrains Mono 11px

- `apps/web/src/components/chat/DateDivider.jsx` — Horizontal rule with centered label
  - Flex row, align center, gap 12px, padding 12px 0, margin 4px 0
  - Lines: flex 1, height 1px, gradient (transparent -> border / border -> transparent)
  - Label: Rajdhani 700 14px, letter-spacing 0.14em, uppercase, text-muted

### Depends On
PR #UI-2, #UI-3

### Verification
- Join messages show green dot, leave shows muted dot
- Error messages render with warning triangle and tinted background
- Info messages show BoltIcon without glow
- Date dividers display centered label between gradient lines

---

## PR #UI-8c: Tool Approval Cards

### Goal
Inline approval cards in the chat timeline with approve/deny/policy UI.

### Scope
- `apps/web/src/components/chat/ToolApprovalCard.jsx` — Inline approval card
  - Same avatar layout as agent messages (30px circle + AgentLogo)
  - Card: flex 1, max-width 80%, border-radius 12px, overflow hidden
  - Top accent: 2px bar, full opacity pending, 40% resolved

  **Colors by state:** Pending -> warning (#F59E0B), Approved -> success (#00FFA3), Denied -> error (#FF4D6D)

  **Shield icon by state:** Pending -> ShieldIcon, Approved -> ShieldCheckIcon, Denied -> ShieldXIcon

  **Header:** padding 10px 14px, flex, gap 8px, flex-wrap
  - Shield icon (16px) + agent name (Rajdhani 700 15px) + status badge (Rajdhani 700 12px) + timestamp

  **Command block:** bg-app, 1px border, border-radius 6px, padding 8px 12px
  - JetBrains Mono 14px, `$ ` prefix in text-muted

  **Reason:** Source Sans 3 15px, text-secondary, line-height 1.5

  **APPROVE button:** flex 1, padding 8px, border-radius 7px, success bg 15%, border 35%, Rajdhani 700 15px. Hover: bg 25%, border 60%, box-shadow `0 0 16px success30`

  **DENY button:** same but error colors. Hover: bg 20%, border 50%

  **"Always approve" button:** 4px 10px, border-radius 5px, ghost. ShieldCheckIcon. Hover: blue

  **"View context" button:** same. EyeIcon. Hover: purple

  **Auto-approve policy dropdown:** margin-top 8px, bg-elevated, 1px border, border-radius 8px, padding 10px 12px. Header: Rajdhani 700 12px blue uppercase "AUTO-APPROVE POLICY". 3 rows: label Source Sans 3 15px text-primary, desc 13px text-muted. Hover bg: blue 10%

- `apps/web/src/components/chat/PendingApprovalPill.jsx` — Count badge for top bar
  - Flex, gap 5px, padding 4px 10px 4px 8px, border-radius 8px
  - Background: warning 12%, border: 1px solid warning 30%
  - ShieldIcon 15px warning + Rajdhani 700 14px warning "N PENDING"
  - Animation: pulse
  - Returns null when count = 0

### Depends On
PR #UI-2, #UI-3

### Verification
- Tool approval cards show correct state colors (pending/approved/denied)
- Approve/deny buttons render for pending state only
- Auto-approve policy dropdown toggles open/closed
- PendingApprovalPill shows count and hides when 0

---

## PR #UI-9: Chat Timeline & Thinking Strip

### Goal
Scrollable message list with auto-scroll, session banner, thinking indicator.

### Scope
- `apps/web/src/components/chat/ChatTimeline.jsx` — Scrollable message list
  - Renders messages by type: date_divider -> DateDivider, system -> SystemMessage, tool_approval -> ToolApprovalCard, default -> MsgBubble
  - Flex 1, overflow auto, padding 20px 24px

- `apps/web/src/components/chat/SessionBanner.jsx` — Active session indicator
  - Flex row, centered, gap 10px, padding 8px 0, margin-bottom 20px
  - Gradient lines: flex 1, height 1px
  - Pill: border-radius 20px, bg success 08, border 1px success 20, box-shadow `0 0 16px success12`
  - Inside: BoltIcon 15px + "SESSION ACTIVE" Orbitron 12px 700 + vertical dividers + session ID JetBrains Mono 12px + agent count Rajdhani 12px 600 warning

- `apps/web/src/components/chat/AgentThinkingStrip.jsx` — Multi-agent thinking indicator
  - Border-top: 1px solid border (when visible)
  - Padding: 6px 20px, flex row, gap 14px
  - Per agent: pulsing Dot (6px) + Source Sans 3 15px ("{Agent} is {status}...")
  - Collapses to 0 height when empty

### Depends On
PR #UI-8a, #UI-8b, #UI-8c, #UI-3

### Verification
- Messages render correctly by type
- Auto-scroll to bottom on new messages
- Thinking strip shows/hides with animation

---

## PR #UI-10: Composer with Slash Commands & @Mentions

### Goal
Rich composer with slash command popup, @mention popup with @all, gradient send button.

### Scope
- `apps/web/src/components/chat/Composer.jsx` — Full composer with autocomplete popups

  **Input bar:**
  - Flex row, gap 8px
  - Background: bg-input at E0, backdrop-filter: blur(8px)
  - Border: 1px solid border -> **purple 60% + glow when popup open** (box-shadow: `0 0 12px purple20`)
  - Border-radius: 10px, padding: 3px 5px 3px 14px

  **Input field:** flex 1, transparent bg, no border, text-primary, Source Sans 3 16px
  - Placeholder: "Type a message... (use @name to mention agents)"

  **SEND button:**
  - Padding: 8px 20px, border-radius: 7px, gradient bg, white text
  - Font: Orbitron 700 14px, letter-spacing 0.06em
  - Box-shadow: `0 0 16px blue50, 0 0 32px purple25, inset 0 1px 0 rgba(255,255,255,0.15)`
  - Shimmer overlay: absolute inset, linear-gradient, background-size 200%, shimmer 2s infinite
  - Content: BoltIcon 15px white + "SEND"

  **Helper text:** margin-top 5px, Source Sans 3 13px, text-muted. `/` and `@` highlighted in purple

  **Slash command popup (14 commands):**
  - Position: absolute, bottom: 100%, full width of composer
  - Background: bg-surface, border: 1px solid border, border-radius: 10px
  - Max-height: 320px, overflow auto, z-index: 80
  - Sticky header: "COMMANDS" Rajdhani 700 12px uppercase text-muted
  - Row: padding 8px 14px, flex, gap 10px
  - Selected: purple bg 12%, border-left 2px solid purple
  - Command: JetBrains Mono 15px purple 600
  - Description: Source Sans 3 15px text-muted
  - **14 commands:** /artchallenge, /hatmaking, /roastreview, /poetry haiku, /poetry limerick, /poetry sonnet, /summary, /continue, /clear, /session start, /session end, /jobs list, /rules remind (+ one more if needed from JSX)

  **@Mention popup:**
  - Same container styling as slash popup
  - Header: "MENTION AN AGENT"
  - **@all row (index 0 when visible):**
    - UsersIcon 13px in 24px purple-tinted circle
    - "@all" Source Sans 3 16px purple 600
    - "All agents in channel" 14px text-muted
    - Bottom border separator
    - Selected: purple bg 10%, purple left border
  - **Agent rows (7 agents):**
    - AgentLogo in 24px tinted circle
    - "@{Label}" 16px agent-color 500
    - "AI Agent" 14px text-muted
    - Selected: agent-color bg 10%, agent-color left border
  - **Keyboard index offsets by +1 when @all row is visible** — when "all".includes(filter) is true, the @all row occupies index 0 and agent rows start at index 1. Selection logic must account for this offset.

  **Additional buttons:** Voice (MicIcon), Schedule (ClockIcon)

### Depends On
PR #UI-2, #UI-3, #UI-5

### Verification
- Typing `/` shows slash command popup with 14 commands
- Typing `@` shows mention popup with @all row + 7 agents
- Arrow keys navigate, Tab/Enter selects
- Keyboard index correctly offsets when @all is visible
- Send button has shimmer animation
- Input border turns purple with glow when popup is open

---

## PR #UI-11: Activity Panel

### Goal
Agent terminal output panel with collapsible rows, collapsed preview, and full log view.

### Scope
- `apps/web/src/components/panels/ActivityPanel.jsx` — Two-view panel (normal + full log)
  - **Width: 380px**, bg-surface, border-left 1px solid border
  - Gradient top bar (2px), ElectricPulse on left edge (vertical, purple, 4-12s delay)
  - Header: BoltIcon + "ACTIVITY" Orbitron 700 15px + "{N} active" JetBrains Mono 12px success

  **Agent row (collapsed):**
  - Chevron (12px, agent-color, rotates 90 deg when open)
  - Dot (7px, agent-color, pulsing)
  - Agent name: Rajdhani 700 16px agent-color uppercase
  - StatusTag
  - Elapsed: JetBrains Mono 12px text-muted, right-aligned
  - **Preview line:** below header, **padding 0 16px 10px 42px** (indented past chevron/dot). JetBrains Mono 12px, output-type color, truncated with ellipsis, 70% opacity

  **Agent row (expanded):**
  - Task card: padding 8px 12px, bg-elevated, border-radius 6px, border. Task name Source Sans 3 15px + file path JetBrains Mono 12px muted
  - Terminal output: bg-app, border, border-radius 6px, **max-height 180px**, overflow auto. JetBrains Mono 13px, line-height 1.7. Each line: timestamp (muted, min-width 30px) + colored text. Hover highlight: agent-color 08
  - **Output colors:** info -> text-secondary, cmd -> blue, ok -> success, warn -> warning, err -> error
  - Action buttons: PauseIcon, ShuffleIcon, TerminalIcon (Full log) — each with label text, border ghost style, hover: agent-color

  **Full log view (replaces panel body):**
  - Header: back chevron (left-pointing, 15px) + AgentLogo (18px) + "{AGENT} LOG" Orbitron 700 15px agent-color
  - Task info bar: bg agent-color 04, padding 10px 16px, border-bottom. Task name + StatusTag + elapsed
  - Terminal: flex 1, **no max-height cap**, bg-app, JetBrains Mono 14px, line-height 1.8
  - Bottom bar: padding 10px 16px, border-top, bg-surface. Two buttons (Pause + Reassign) with icons

### Depends On
PR #UI-2, #UI-3, #UI-4, #UI-5

### Verification
- Collapsible agent rows expand/collapse with chevron rotation
- Collapsed rows show preview line of latest output
- Full log view replaces normal view with back button
- Terminal lines color-coded by type

---

## PR #UI-12: Agents Panel

### Goal
Per-channel agent process manager with start/stop styling, system prompt modes, spawn button, add agent flow.

### Scope
- `apps/web/src/components/panels/AgentsPanel.jsx`
  - **Width: 360px**, same chrome as Activity (gradient bar, electric pulse)
  - Header: UsersIcon + "AGENTS" Orbitron 700 15px + "{N} running" JetBrains Mono 12px
  - Channel context bar: "Channel" label 14px muted + "#channelname" 16px text-primary 500

  **Agent card:**
  - Avatar: 32x32px circle, agent-color 15% bg, 1.5px border (agent-color 50% when running, border when stopped)
  - Name: Rajdhani 700 16px agent-color uppercase + Dot (6px, success/muted) + "running"/"stopped" JetBrains Mono 12px
  - PID + uptime: JetBrains Mono 12px muted (only when running)
  - Opacity: 1 when running, 0.6 when stopped

  **Start/Stop button:** 32x32px, border-radius 8px
  - **Start:** success bg 12%, success border 30%, PlayIcon 12px. Hover: bg 25%, box-shadow glow `0 0 12px success30`
  - **Stop:** error bg 12%, error border 30%, StopIcon 15px. Hover: bg 25%, box-shadow glow `0 0 12px error30`

  **Repo dropdown:** full width, bg-input, 1px border, border-radius 5px, JetBrains Mono 14px. Focus: agent-color border

  **System prompt (collapsed mode):** bg-app, 1px border, border-radius 5px, Source Sans 3 14px text-secondary, max-height 42px, overflow hidden, fade gradient at bottom (linear-gradient transparent -> bg-app). Click to edit.

  **System prompt (editing mode):** textarea, 4 rows, bg-input, border 1px agent-color 40%, Source Sans 3 14px, resize vertical

  **Remove button:** only when stopped. border ghost, TrashIcon + "Remove from channel". Hover: error

  **Add agent flow:**
  - Trigger: "+ Add agent to #{channel}" dashed border button, blue 40%, PlusIcon
  - Agent type picker: flex row, each agent (from `allAgentTypes` not already assigned) as a selectable card (flex 1, padding 8px, border-radius 7px, AgentLogo + label). Selected: agent-bg 15%, agent-border 50%
  - Repo picker: dropdown, same as agent card
  - System prompt: textarea, 3 rows
  - Cancel button: ghost border
  - **SPAWN button:** gradient + shimmer (same as SEND), PowerIcon, disabled until type + repo selected

### Depends On
PR #UI-2, #UI-3, #UI-4, #UI-5

### Verification
- Start/stop buttons toggle agent state with correct styling
- Start button: green, stop button: red
- System prompt shows collapsed (fade gradient) and editing (textarea) modes
- Add agent flow works end-to-end
- Spawn button disabled until type + repo selected

---

## PR #UI-13: Jobs, Rules & Settings Panels + RightPanel Wrapper

### Goal
Three simpler panels plus the shared RightPanel wrapper.

### Scope
- `apps/web/src/components/panels/RightPanel.jsx` — Shared wrapper
  - Same chrome: gradient top bar (2px), ElectricPulse vertical, header with icon + title + close x
  - Panels declare their own width

- `apps/web/src/components/panels/JobsPanel.jsx` — **Width: 380px**
  - Empty state: dashed border card, "+ Create your first job", Source Sans 3 15px muted
  - Status groups: TO DO / ACTIVE / CLOSED with colored headers

- `apps/web/src/components/panels/RulesPanel.jsx` — **Width: 380px**
  - "Remind agents" button top-right, purple tint
  - Empty state: dashed card "+ No rules yet"

- `apps/web/src/components/panels/SettingsPanel.jsx` — **Width: 380px**
  - Sections: Profile (Name, Font, Contrast), Behavior (Loop guard, Rule refresh), Notifications (Desktop, Sounds toggle), Sounds (Default sound)
  - Input fields: bg-input, 1px border, border-radius 5px. Focus: blue border + box-shadow `0 0 12px blue30`
  - **Toggle switch exact spec:**
    - Track: **40x22px**, border-radius: 11px
    - Off: bg-input, 1px solid border
    - On: gradient bg, transparent border, box-shadow `0 0 14px blue50`
    - Circle: **16x16px** white, top: 2px, left: **3px** (off) / **21px** (on), transition: left 0.2s ease
    - On circle glow: `0 0 8px blue80`
  - **APPLY button:** gradient + shimmer + BoltIcon (same as SEND)
  - Cancel: ghost border

### Depends On
PR #UI-2, #UI-3, #UI-4, #UI-5

### Verification
- Each panel slides in from right
- Settings toggle switches match exact spec (40x22 track, 16x16 circle, correct positions)
- Rules shows "Remind agents" button
- All panels respect their 380px/380px/380px widths

---

## PR #UI-14: Modals (Session Launcher & Schedule)

### Goal
Modal system: generic wrapper, Session Launcher, Schedule Modal.

### Scope
- `apps/web/src/components/modals/Modal.jsx` — Dark overlay with centered card
  - **Overlay:** absolute inset, **rgba(0,0,0,0.6)**, **backdrop-filter: blur(4px)**, z-index **200**
  - **Card:** bg-elevated, 1px border, border-radius **14px**, max-width **480px**, width **90%**, max-height **80vh**, overflow auto
  - Gradient top accent bar (2px, gradient, 50% opacity, border-radius top)
  - Close button: absolute top 14px right 16px, text-muted, font-size 18, z-index 1
  - Entry animation: **modalIn 0.25s ease**
  - Close: overlay click or **Escape key**

- `apps/web/src/components/modals/SessionLauncher.jsx` — Session type grid
  - Header: "Start a Session" **Orbitron 20px 700** + BoltIcon 20px
  - Goal input: full width, bg-input, 1px purple border 40%, border-radius 8px, Source Sans 3 16px, box-shadow `0 0 8px purple15`
  - **Session types (4 cards with roles):**
    1. **Code Review** — roles: builder, reviewer, red_team, synthesiser
    2. **Debate** — roles: proposer, for, against, moderator
    3. **Design Critique** — roles: presenter, critic, synthesiser
    4. **Planning** — roles: planner, challenger, synthesiser
  - Card: Rajdhani 700 18px name, Source Sans 3 15px desc, RoleTag pills
  - Custom session: "Design a session" section with agent dropdown + text input
  - Launch button: gradient + shimmer

- `apps/web/src/components/modals/ScheduleModal.jsx` — Date/time picker
  - Header: "SCHEDULE MESSAGE" Orbitron 20px 700
  - Textarea for message, date/time picker, send button

### Depends On
PR #UI-2, #UI-3

### Verification
- Modal opens with backdrop blur and modalIn entry animation
- Escape key and overlay click close modal
- Session launcher shows 4 session types with correct role pills
- Modal card respects max-width 480px, max-height 80vh

---

## PR #UI-15: Integration & Cleanup

### Goal
Wire all new components to data layer, remove old components.

### Scope
- Refactor `apps/web/src/App.jsx` and `apps/web/src/components/ChannelShell.jsx`
- Remove replaced components (SidebarChannelList, ChannelHeader, ChatShell, etc.)
- Wire WebSocket events to new components

### Concrete Integration Checklist

- [ ] `App.jsx` renders `<AppShell>` with `<Sidebar>`, `<TopBar>`, `<ChatTimeline>`, `<Composer>`, `<AgentThinkingStrip>`
- [ ] Panel state (`activePanel`) lives in App or a Zustand store; TopBar toolbar buttons call `togglePanel(name)`
- [ ] `<RightPanel>` wrapper renders the correct panel component based on `activePanel` value
- [ ] Panel widths enforced: Activity 380px, Agents 360px, Jobs 380px, Rules 380px, Settings 380px
- [ ] Sidebar `<ChannelList>` calls existing `useChannelStore` (or equivalent) for channel switching, creation, deletion
- [ ] Sidebar `<RepoList>` wires to repo data source
- [ ] `<ChatTimeline>` maps over message store, dispatches to MessageBubble / SystemMessage / ToolApprovalCard / DateDivider by `msg.type`
- [ ] `<Composer>` calls `sendMessage` action on submit; slash commands dispatch to appropriate handlers
- [ ] `<AgentThinkingStrip>` reads from agent status store or WebSocket events
- [ ] `<SessionBanner>` reads active session from session store
- [ ] `<PendingApprovalPill>` counts pending tool_approval messages
- [ ] `<ToolApprovalCard>` approve/deny buttons dispatch approval actions via WebSocket/API
- [ ] `<AgentsPanel>` start/stop/add/remove agent actions dispatch to agent process API
- [ ] `<SessionLauncher>` launch action dispatches session creation
- [ ] `<ScheduleModal>` schedule action dispatches scheduled message creation
- [ ] `<SettingsPanel>` reads/writes user settings store
- [ ] All old components removed: `SidebarChannelList`, `ChannelHeader`, `ChatShell`, `RuntimeDetailsPanel`, old `MessageCard`
- [ ] `allAgentTypes` and `agentMeta` imported from `apps/web/src/constants/agents.js` everywhere (no duplicate definitions)
- [ ] Background effects (`ParticleField`, `AmbientOrbs`) rendered in AppShell behind content
- [ ] `npm run build` succeeds with no warnings
- [ ] Full manual smoke test: channel switch, send message, open each panel, open each modal, agent start/stop

### Depends On
All previous UI PRs

### Verification
- Full app renders with design-matching UI
- Channel switching, messaging, WebSocket updates all work
- All panels open/close from top bar
- All modals open/close correctly
- `npm run build` succeeds

---

## Dependency Graph

```text
PR #UI-1 (Tokens) <- foundation
  ├── PR #UI-2 (Icons)
  │     └── PR #UI-3 (Primitives + constants/agents.js)
  └── PR #UI-4 (Effects)

PR #UI-5 (App Shell) <- needs #UI-4
  ├── PR #UI-6  (Sidebar) <- needs #UI-2, #UI-3, #UI-5
  ├── PR #UI-7  (Top Bar) <- needs #UI-2, #UI-3, #UI-4, #UI-5
  ├── PR #UI-11 (Activity) <- needs #UI-2, #UI-3, #UI-4, #UI-5
  ├── PR #UI-12 (Agents) <- needs #UI-2, #UI-3, #UI-4, #UI-5
  └── PR #UI-13 (Jobs/Rules/Settings) <- needs #UI-2, #UI-3, #UI-4, #UI-5

PR #UI-8a (Message Bubble) <- needs #UI-2, #UI-3
PR #UI-8b (System Messages) <- needs #UI-2, #UI-3
PR #UI-8c (Tool Approvals) <- needs #UI-2, #UI-3
  └── PR #UI-9 (Timeline) <- needs #UI-8a, #UI-8b, #UI-8c, #UI-3

PR #UI-10 (Composer) <- needs #UI-2, #UI-3, #UI-5
PR #UI-14 (Modals) <- needs #UI-2, #UI-3

PR #UI-15 (Integration) <- needs ALL above
```

## Parallelizable Work

**Phase 1** (sequential): #UI-1 -> #UI-2 -> #UI-3, and #UI-1 -> #UI-4
**Phase 2** (parallel after Phase 1): #UI-5, #UI-8a, #UI-8b, #UI-8c, #UI-14
**Phase 3** (parallel after #UI-5): #UI-6, #UI-7, #UI-9, #UI-10, #UI-11, #UI-12, #UI-13
**Phase 4** (final): #UI-15
