# THE DUCKDOME — Design Spec Reference

> **Source of truth:** `design/the-duckdome.jsx`
> **Updated:** 2026-03-29
> **Font scale:** Bumped — body 16px, labels 14-15px, timestamps 11px, display 20-22px

---

## 1. Design Tokens

### 1.1 Color Palette

```
SURFACES
  --bg-app:       #0D1117
  --bg-surface:   #111827
  --bg-elevated:  #1A2233
  --bg-sidebar:   #0B1020
  --bg-input:     #0F172A

TEXT
  --text-primary:   #E6EDF3
  --text-secondary: #9CA3AF
  --text-muted:     #6B7280
  --text-bright:    #F8FAFC

BRAND
  --blue:        #00D4FF
  --purple:      #A855F7
  --purple-glow: #C084FC
  --gradient:    linear-gradient(90deg, #00D4FF 0%, #A855F7 100%)

STATUS
  --success: #00FFA3
  --warning: #F59E0B
  --error:   #FF4D6D
  --info:    #38BDF8

BORDER
  --border: #1F2937
```

### 1.2 Agent Colors

Each agent gets a primary color, a tinted background (primary at 6% opacity), and a border (primary at 22% opacity). Kilo is slightly different (5%/18%) because pure yellow is visually louder.

```
  Agent     Primary     bg                          border
  ───────── ─────────── ─────────────────────────── ───────────────────────────
  Claude    #FF8A5C     rgba(255,138,92, 0.06)      rgba(255,138,92, 0.22)
  Codex     #00FFAA     rgba(0,255,170, 0.06)       rgba(0,255,170, 0.22)
  Gemini    #6BAAFF     rgba(107,170,255, 0.06)     rgba(107,170,255, 0.22)
  Kimi      #3D9EFF     rgba(61,158,255, 0.06)      rgba(61,158,255, 0.22)
  Qwen      #A78BFF     rgba(167,139,255, 0.06)     rgba(167,139,255, 0.22)
  Kilo      #EEFF41     rgba(238,255,65, 0.05)      rgba(238,255,65, 0.18)
  MiniMax   #3DFFC8     rgba(61,255,200, 0.06)      rgba(61,255,200, 0.22)
  User      #A855F7     rgba(168,85,247, 0.06)      rgba(168,85,247, 0.22)
```

### 1.3 Status Colors

```
  PROCESSING → --blue    (#00D4FF)
  ATTACKING  → --error   (#FF4D6D)  + warningFlash animation + BoltIcon
  DEBATING   → --purple  (#A855F7)
  ANALYZING  → --info    (#38BDF8)
  IDLE       → --text-muted (#6B7280)
```

### 1.4 Typography

```
FONTS
  --font-display: 'Orbitron'        — Headers, logo, send button, panel titles
  --font-label:   'Rajdhani'        — Labels, tags, status badges, section headers
  --font-body:    'Source Sans 3'   — Body text, descriptions, inputs
  --font-mono:    'JetBrains Mono'  — Code, timestamps, file paths, terminal output

SCALE (updated)
  22px  — Modal headers, close buttons (Orbitron 700)
  20px  — Panel section headers (Orbitron 700)
  18px  — Session type names, large labels (Rajdhani 700)
  16px  — Body text, message content, inputs, descriptions (Source Sans 3 400-500)
  15px  — Labels, detail text, agent names in panels (Source Sans 3 500 / Rajdhani 700)
  14px  — Code tags, channel names, mono text (JetBrains Mono 400-500)
  13px  — Helper text, secondary labels (Source Sans 3 400)
  12px  — Status tags, section labels, small UI elements (Rajdhani 700)
  11px  — Timestamps (JetBrains Mono 400, often at 50% opacity)
  10px  — Micro labels (rare)

LETTER SPACING
  0.14em — Section labels (CHANNELS, REPOS, COMMANDS)
  0.10em — Status tags (PROCESSING, APPROVED), policy headers
  0.08em — Changes label
  0.06em — Panel titles (ACTIVITY, AGENTS), send button, agent names
  0.04em — Agent names in bubbles, sidebar items
```

### 1.5 Keyframe Animations (16 total)

```
  pulse            — Opacity 0.5 → 1 → 0.5, 1.5s. Used: dots, unread badges, pending pill
  breathe          — Box-shadow intensity oscillation, 3s. Used: logo container
  shimmer          — Background-position -200% → 200%, 2s. Used: send/apply buttons
  fadeUp           — Opacity 0→1, translateY 8px→0, 0.3s. Used: all message entries
  slideIn          — TranslateX 100%→0, opacity 0→1, 0.25s. Used: right panels
  barPulse         — ScaleY 0.2 → 1 → 0.2. Used: waveform bars
  borderGlow       — Border-color cycles blue→purple, 6s. Used: agent strip
  textPulse        — Filter brightness 1 → 1.5 → 1. Used: thinking text
  voltFlash        — Quick opacity flickers, 1s. Used: logo text
  orbFloat         — Gentle translate + scale drift, continuous. Used: ambient orbs
  warningFlash     — Opacity 1 → 0.4 → 1, 1s. Used: ATTACKING status
  shakeSubtle      — 0.5px translate jitter. Used: error states
  glitchX          — TranslateX jitter. Used: glitch effects
  pulseTravelDown  — Top -40px → calc(100%+40px). Used: vertical electric pulse
  pulseTravelRight — Left -60px → calc(100%+60px). Used: horizontal electric pulse
  modalIn          — Scale 0.95→1, translateY 10px→0, opacity 0→1, 0.25s. Used: modals
```

---

## 2. Icon System

### 2.1 SVG Icons (30 icons)

Every icon takes `{size, color}` props. Default color is `currentColor` so they inherit from parent CSS.

```
  ACTIONS:   Reply, Pin, Copy, Check, Trash, Edit
  PANELS:    Jobs, Rules, Gear, Terminal, Users
  MEDIA:     Mic, Clock, Help, Play, Pause
  NAV:       Chevron (with rotation prop), Folder, Cube, Refresh, Plus, Shuffle
  APPROVAL:  Shield, ShieldCheck, ShieldX, Eye, X
  SYSTEM:    Power, Stop
  BRAND:     BoltIcon (separate component, has optional glow filter with feGaussianBlur)
```

### 2.2 Agent Logo SVGs (7 + fallback)

Each takes `{agent, size}`. Reads color from `agentMeta[agent].color`.

```
  Claude   — 4 rotated lines (0°/45°/90°/135°) radiating from center + 2.5r filled circle
  Codex    — Hexagon outline (stroke 1.8) + 3r filled circle center (0.8 opacity)
  Gemini   — 4-point sparkle (4 teardrop paths) + 2r center dot
  Kimi     — Overlapping moon crescent (filled, 0.9 opacity) + 7r circle outline (stroke 1.8)
  Qwen     — Concentric circles (8r + 4r outlines) + 1.5r center dot + 4 crosshair lines
  Kilo     — Angle brackets (< >) stroke 2.2 + diagonal slash (0.7 opacity)
  MiniMax  — Sine wave path (stroke 2) + 2r center dot
  Fallback — First letter of agent name in Orbitron 700 14px
```

---

## 3. Shared Primitives

### Dot
- Size: configurable, default 8px
- Border-radius: 50%
- Box-shadow: `0 0 6px {color}, 0 0 14px {color}60`
- Animation: `pulse 1.5s ease-in-out infinite`

### Waveform
- 16 bars (configurable), 2px wide, gap: 1.5px, height container: 18px
- Each bar: border-radius 1px, color at 70% opacity
- Animation: `barPulse` with random duration (0.3-0.8s) and staggered delay (i*0.04s)

### SectionLabel
- Font: Rajdhani 700, 14px, letter-spacing 0.14em, uppercase
- Prefix dot: 4px circle, box-shadow glow at 8px/16px
- Text-shadow: `0 0 8px {color}50`

### ToolbarBtn
- Size: 32×32px, border-radius: 7px
- Default: transparent bg, transparent border, text-muted color
- Hover: `rgba(255,255,255,0.03)` bg, border-color border, text-primary color
- Active: blue bg at 18%, `1px solid blue` at 60%, blue color, box-shadow `0 0 12px blue35, 0 0 28px blue16`
- Transition: all 0.12s

### CodeTag
- Background: blue at 12%, border: `1px solid blue` at 22%, border-radius: 4px
- Padding: 1px 6px
- Font: JetBrains Mono 14px, blue color

### StatusTag
- Font: Rajdhani 700, 12px, letter-spacing 0.1em
- Padding: 2px 8px, border-radius: 4px
- Background: status-color at 12%, border: `1px solid status-color` at 25%
- ATTACKING variant: adds BoltIcon (12px) and `warningFlash 1s ease infinite`

### RoleTag
- Font: JetBrains Mono 12px
- Padding: 2px 8px, border-radius: 4px
- Background: purple at 15%, border: `1px solid purple` at 30%, color: purple-glow

---

## 4. Layout

### App Shell
- Full viewport, flex row, overflow hidden
- Background: bg-app

### Sidebar
- Width: 228px, min-width: 228px
- Background: bg-sidebar at F0 opacity, backdrop-filter: blur(12px)
- Border-right: 1px solid border
- Flex column, full height, z-index: 2

### Main Content Area
- Flex: 1, flex-column, min-width: 0
- z-index: 2

### Right Panel Slot
- Flex-shrink: 0 (panels declare their own width)
- Slides in with `slideIn 0.25s ease`

---

## 5. Sidebar Components

### Logo Header
- Container: 32×32px, border-radius: 8px, gradient bg (blue30 → purple30), border 1.5px solid blue50
- Box-shadow: `0 0 16px blue35, 0 0 32px purple20`
- Animation: `breathe 3s ease-in-out infinite`
- Title: "THE DUCKDOME" — Orbitron 800, 12px, letter-spacing 0.15em, gradient text (-webkit-background-clip: text), voltFlash animation
- Subtitle: "AI AGENT BATTLEGROUND" — Rajdhani 600, 10px, letter-spacing 0.14em, purple-glow at 40%

### Channel Row
- Padding: 6px 14px 6px 16px, flex row, gap: 8px
- Active: bg blue at 0C opacity, 2px gradient left border (absolute positioned)
- Hash: JetBrains Mono 15px, blue when active, text-muted when not
- Name: Source Sans 3 16px, weight 600/bright when active, weight 400/secondary when not
- Hover delete: `×` button, visible on hover only

### Unread Badge
- Min-width: 18px, height: 18px, border-radius: 9px
- Background: `linear-gradient(135deg, purple, error)`
- Font: Rajdhani 700, 12px, white
- Box-shadow: `0 0 10px purple60`
- Animation: `pulse 1.5s ease-in-out infinite`

### Repo Row
- Padding: 5px 14px 5px 16px, flex row, gap: 7px
- CubeIcon (14px, text-muted) + name in Source Sans 3 15px text-secondary
- Text overflow: ellipsis

### Repos Section Header
- FolderIcon, PlusIcon, RefreshIcon in a row, each at 15px, 50% opacity

### User Footer
- Padding: 10px 16px, border-top: 1px solid border
- Avatar: 24×24px circle, gradient bg, 1.5px border blue40, Orbitron 700 14px "J" initial
- Name: Source Sans 3 500, 16px, text-secondary
- Session button: 26×26px circle, gradient bg, PlayIcon 12px white, box-shadow glow

---

## 6. Top Bar

- Height: 50px, flex row, align center, padding: 0 18px, gap: 10px
- Background: bg-surface at D0 opacity, backdrop-filter: blur(12px)
- Border-bottom: 1px solid border
- Flex-shrink: 0, position: relative
- ElectricPulse on bottom edge (horizontal mode, purple, delay 5-12s)

### Contents (left to right)
1. BoltIcon (16px, blue)
2. Channel name — Orbitron 600, 16px, text-bright, letter-spacing 0.04em
3. Waveform (blue, 12 bars)
4. Flex spacer
5. Agent status strip — clickable row, border-radius 8px, 1px border (blue40 when activity panel open), `borderGlow 6s` animation. Each agent: AgentLogo (16px) with 5px status dot overlay (green when running, muted when stopped), agent name in Source Sans 3 14px
6. PendingApprovalPill (between agent strip and toolbar)
7. Toolbar buttons row (gap: 3px): Activity (BoltIcon), Agents (UsersIcon), Jobs (JobsIcon), Rules (RulesIcon), Pinned (PinIcon), Settings (GearIcon), Help (HelpIcon)

### Agent Status Dot Overlay
- Position: absolute, bottom: -1px, right: -1px
- Size: 5×5px, border-radius: 50%
- Green (success) when running, text-muted when stopped
- Border: 1.5px solid bg-surface (creates gap between dot and logo)
- Box-shadow: `0 0 4px success` when running

---

## 7. Message System

### 7.1 Message Bubble

**Agent messages (left-aligned):**
- Avatar: 30×30px circle, bg agent-color 15%, border 1.5px agent-color 50%, AgentLogo 18px
- Margin-right: 12px, margin-top: 2px
- Bubble max-width: 72%
- Border-radius: 14px 14px 14px 4px (flat corner near avatar)

**User messages (right-aligned):**
- No avatar
- Bubble max-width: 62%
- Border-radius: 14px 14px 4px 14px

**Bubble shared:**
- Background: agent-bg (6% tinted)
- Border: 1px solid agent-border (22%) — **brightens to 40% on hover**
- Padding: 12px 16px
- Position: relative
- Transition: border-color 0.15s
- Margin-bottom: 18px → **32px on hover** (transition: 0.12s) — makes room for toolbar
- Entry animation: `fadeUp 0.3s ease {idx*0.06}s both`

**Header row:** flex, gap 8px, flex-wrap: wrap
- Agent name: Rajdhani 700, 15px, agent-color, uppercase, letter-spacing 0.04em
- StatusTag
- Timestamp: JetBrains Mono, 12px, text-muted
- "choose a role" button: appears on hover. Padding 2px 8px, border-radius 4px. Default: transparent/border/muted. Hover: purple border/text. Open: purple bg 15%, purple border 60%

**Body:** Source Sans 3 16px, line-height 1.6, text-primary
- @mentions split via `/@\w+/` regex → blue color, blue bg 10%, border-radius 3px, padding 1px 4px, weight 500

**Details section (optional):**
- Divider: 1px line, agent-color 18%, margin-bottom 7px
- Label: "Changes:" — Rajdhani 12px uppercase, agent-color, BoltIcon 12px
- Items: 4px dot bullet (agent-color, 60% opacity) + Source Sans 3 15px text-secondary
- Inline code: backtick pattern split → CodeTag component

### 7.2 Message Toolbar (floating)
- Position: absolute, bottom: -16px, right: 12px
- Background: bg-elevated, border: 1px solid border, border-radius: 6px, padding: 2px
- Box-shadow: 0 4px 16px rgba(0,0,0,0.5)
- Opacity/transform transition: 0.12s, pointer-events: none when hidden
- z-index: 50

**Buttons (28×28px each, border-radius 5px):**
1. Reply (ReplyIcon 13px)
2. Pin (PinIcon 13px)
3. Copy (CopyIcon 13px) → on click: swaps to CheckIcon, turns success, "Copied!" tooltip (absolute top: -22px, centered, success bg, black text, 12px 600, border-radius 4px, fadeUp 0.2s). Reverts after 1.8s.
4. Convert to Job (BoltIcon 14px)
5. 1px vertical divider (height 16px, border color, margin 0 2px)
6. Delete (TrashIcon 13px) — hover: red bg rgba(255,77,109,0.15), error color

### 7.3 Role Dropdown
- Position: absolute, top: 28px, left: 0, z-index: 120
- Background: bg-surface, border: 1px solid border, border-radius: 10px
- Padding: 12px, min-width: 260px
- Box-shadow: 0 8px 32px rgba(0,0,0,0.6), 0 0 20px blue08

**Roles (text only, NO emojis):**
None (pre-selected: blue bg 30%, blue border 60%), Planner, Designer, Architect, Builder, Reviewer, Researcher, Red Team, Wry, Unhinged, Hype

- Pill style: padding 5px 12px, border-radius 16px, bg-elevated, 1px border, Source Sans 3 15px
- Custom input at bottom: full width, border-radius 8px, bg-input

### 7.4 System Messages

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

### 7.5 Date Divider
- Flex row, align center, gap 12px, padding 12px 0, margin 4px 0
- Lines: flex 1, height 1px, gradient (transparent → border / border → transparent)
- Label: Rajdhani 700 14px, letter-spacing 0.14em, uppercase, text-muted

### 7.6 Tool Approval Card
- Same avatar layout as agent messages (30px circle + AgentLogo)
- Card: flex 1, max-width 80%, border-radius 12px, overflow hidden
- Top accent: 2px bar, full opacity pending, 40% resolved

**Colors by state:**
- Pending: warning (#F59E0B)
- Approved: success (#00FFA3)
- Denied: error (#FF4D6D)

**Shield icon by state:**
- Pending: ShieldIcon
- Approved: ShieldCheckIcon
- Denied: ShieldXIcon

**Header:** padding 10px 14px, flex, gap 8px, flex-wrap
- Shield icon (16px) + agent name (Rajdhani 700 15px) + status badge (Rajdhani 700 12px) + timestamp

**Command block:** bg-app, 1px border, border-radius 6px, padding 8px 12px
- JetBrains Mono 14px, `$ ` prefix in text-muted

**Reason:** Source Sans 3 15px, text-secondary, line-height 1.5

**APPROVE button:** flex 1, padding 8px, border-radius 7px, success bg 15%, border 35%, Rajdhani 700 15px
- Hover: bg 25%, border 60%, box-shadow `0 0 16px success30`

**DENY button:** same but error colors
- Hover: bg 20%, border 50%

**"Always approve" button:** 4px 10px, border-radius 5px, ghost. ShieldCheckIcon. Hover: blue
**"View context" button:** same. EyeIcon. Hover: purple

**Auto-approve policy dropdown:** margin-top 8px, bg-elevated, 1px border, border-radius 8px, padding 10px 12px
- Header: Rajdhani 700 12px blue uppercase "AUTO-APPROVE POLICY"
- 3 rows: label Source Sans 3 15px text-primary, desc 13px text-muted
- Hover bg: blue 10%

### 7.7 PendingApprovalPill
- Flex, gap 5px, padding 4px 10px 4px 8px, border-radius 8px
- Background: warning 12%, border: 1px solid warning 30%
- ShieldIcon 15px warning + Rajdhani 700 14px warning "N PENDING"
- Animation: pulse
- Returns null when count = 0

### 7.8 Agent Thinking Strip
- Border-top: 1px solid border (when visible)
- Padding: 6px 20px, flex row, gap 14px
- Per agent: pulsing Dot (6px) + Source Sans 3 15px ("{Agent} is {status}...")
- Collapses to 0 height when empty

### 7.9 Session Banner
- Flex row, centered, gap 10px, padding 8px 0, margin-bottom 20px
- Gradient lines: flex 1, height 1px
- Pill: border-radius 20px, bg success 08, border 1px success 20, box-shadow `0 0 16px success12`
- Inside: BoltIcon 15px + "SESSION ACTIVE" Orbitron 12px 700 + vertical dividers + session ID JetBrains Mono 12px + agent count Rajdhani 12px 600 warning

---

## 8. Composer

### Input Bar
- Flex row, gap 8px
- Background: bg-input at E0, backdrop-filter: blur(8px)
- Border: 1px solid border → **purple 60% + glow when popup open**
- Border-radius: 10px, padding: 3px 5px 3px 14px
- Box-shadow when popup open: `0 0 12px purple20`

### Input Field
- Flex 1, transparent bg, no border, text-primary, Source Sans 3 16px
- Placeholder: "Type a message... (use @name to mention agents)"

### SEND Button
- Padding: 8px 20px, border-radius: 7px, gradient bg, white text
- Font: Orbitron 700 14px, letter-spacing 0.06em
- Box-shadow: `0 0 16px blue50, 0 0 32px purple25, inset 0 1px 0 rgba(255,255,255,0.15)`
- Shimmer overlay: absolute inset, `linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent)`, background-size 200%, shimmer 2s infinite
- Content: BoltIcon 15px white + "SEND"

### Helper Text
- Margin-top: 5px, Source Sans 3 13px, text-muted
- `/` and `@` highlighted in purple

### Slash Command Popup
- Position: absolute, bottom: 100%, full width of composer
- Background: bg-surface, border: 1px solid border, border-radius: 10px
- Max-height: 320px, overflow auto
- Box-shadow: `0 -8px 32px rgba(0,0,0,0.6)`, margin-bottom: 4px, z-index: 80
- Sticky header: "COMMANDS" Rajdhani 700 12px uppercase text-muted
- Row: padding 8px 14px, flex, gap 10px
- Selected: purple bg 12%, border-left 2px solid purple
- Command: JetBrains Mono 15px purple 600
- Description: Source Sans 3 15px text-muted

**14 commands:**
/artchallenge, /hatmaking, /roastreview, /poetry haiku, /poetry limerick, /poetry sonnet, /summary, /continue, /clear, /session start, /session end, /jobs list, /rules remind

### @Mention Popup
- Same container styling as slash popup
- Header: "MENTION AN AGENT"

**@all row (index 0 when visible):**
- UsersIcon 13px in 24px purple-tinted circle
- "@all" Source Sans 3 16px purple 600
- "All agents in channel" 14px text-muted
- Bottom border separator
- Selected: purple bg 10%, purple left border

**Agent rows (7 agents):**
- AgentLogo in 24px tinted circle
- "@{Label}" 16px agent-color 500
- "AI Agent" 14px text-muted
- Selected: agent-color bg 10%, agent-color left border

Keyboard index offsets by +1 when @all row is visible.

---

## 9. Activity Panel

- Width: 380px, bg-surface, border-left 1px solid border
- Gradient top bar (2px), ElectricPulse on left edge (vertical, purple, 4-12s delay)
- Header: BoltIcon + "ACTIVITY" Orbitron 700 15px + "{N} active" JetBrains Mono 12px success

### Agent Row (collapsed)
- Chevron (12px, agent-color, rotates 90° when open)
- Dot (7px, agent-color, pulsing)
- Agent name: Rajdhani 700 16px agent-color uppercase
- StatusTag
- Elapsed: JetBrains Mono 12px text-muted, right-aligned
- **Preview line:** below header, padding 0 16px 10px 42px (indented past chevron/dot). JetBrains Mono 12px, output-type color, truncated with ellipsis, 70% opacity

### Agent Row (expanded)
- Task card: padding 8px 12px, bg-elevated, border-radius 6px, border. Task name Source Sans 3 15px + file path JetBrains Mono 12px muted
- Terminal output: bg-app, border, border-radius 6px, max-height 180px, overflow auto. JetBrains Mono 13px, line-height 1.7. Each line: timestamp (muted, min-width 30px) + colored text. Hover highlight: agent-color 08

**Output colors:** info → text-secondary, cmd → blue, ok → success, warn → warning, err → error

- Action buttons: PauseIcon, ShuffleIcon, TerminalIcon — each with label text, border ghost style, hover: agent-color

### Full Log View (replaces panel body)
- Header: back chevron (left-pointing, 15px) + AgentLogo (18px) + "{AGENT} LOG" Orbitron 700 15px agent-color
- Task info bar: bg agent-color 04, padding 10px 16px, border-bottom. Task name + StatusTag + elapsed
- Terminal: flex 1, no max-height cap, bg-app, JetBrains Mono 14px, line-height 1.8
- Bottom bar: padding 10px 16px, border-top, bg-surface. Two buttons (Pause + Reassign) with icons

---

## 10. Agents Panel

- Width: 360px, same chrome as Activity (gradient bar, electric pulse)
- Header: UsersIcon + "AGENTS" Orbitron 700 15px + "{N} running" JetBrains Mono 12px
- Channel context bar: "Channel" label 14px muted + "#channelname" 16px text-primary 500

### Agent Card
- Avatar: 32×32px circle, agent-color 15% bg, 1.5px border (agent-color 50% when running, border when stopped)
- Name: Rajdhani 700 16px agent-color uppercase + Dot (6px, success/muted) + "running"/"stopped" JetBrains Mono 12px
- PID + uptime: JetBrains Mono 12px muted (only when running)
- Opacity: 1 when running, 0.6 when stopped

**Start/Stop button:** 32×32px, border-radius 8px
- Start: success bg 12%, success border 30%, PlayIcon 12px. Hover: bg 25%, glow
- Stop: error bg 12%, error border 30%, StopIcon 15px. Hover: bg 25%, glow

**Repo dropdown:** full width, bg-input, 1px border, border-radius 5px, JetBrains Mono 14px. Focus: agent-color border

**System prompt (collapsed):** bg-app, 1px border, border-radius 5px, Source Sans 3 14px text-secondary, max-height 42px, overflow hidden, fade gradient at bottom. Click to edit.

**System prompt (editing):** textarea, 4 rows, bg-input, border 1px agent-color 40%, Source Sans 3 14px, resize vertical

**Remove button:** only when stopped. border ghost, TrashIcon + "Remove from channel". Hover: error

### Add Agent Flow
- Trigger: "+ Add agent to #{channel}" dashed border button, blue 40%, PlusIcon
- Agent type picker: flex row, each agent as a selectable card (flex 1, padding 8px, border-radius 7px, AgentLogo + label). Selected: agent-bg 15%, agent-border 50%
- Repo picker: dropdown, same as agent card
- System prompt: textarea, 3 rows
- Cancel button: ghost border. SPAWN button: gradient + shimmer (same as SEND), PowerIcon, disabled until type + repo selected

---

## 11. Jobs, Rules & Settings Panels

### RightPanel Wrapper
- Same chrome: gradient top bar (2px), ElectricPulse vertical, header with icon + title + close ×

### JobsPanel (width: 380px)
- Empty state: dashed border card, "+ Create your first job", Source Sans 3 15px muted
- Status groups: TO DO / ACTIVE / CLOSED with colored headers

### RulesPanel (width: 380px)
- "Remind agents" button top-right, purple tint
- Empty state: dashed card "+ No rules yet"

### SettingsPanel (width: 380px)
- Sections: Profile (Name, Font, Contrast), Behavior (Loop guard, Rule refresh), Notifications (Desktop, Sounds toggle), Sounds (Default sound)
- Input fields: bg-input, 1px border, border-radius 5px. Focus: blue border + box-shadow `0 0 12px blue30`
- Toggle: 40×22px track, border-radius 11px. Off: bg-input, 1px border. On: gradient bg, transparent border, box-shadow `0 0 14px blue50`. Circle: 16×16px white, top 2px, left 3px (off) / 21px (on), transition 0.2s ease. On glow: `0 0 8px blue80`
- APPLY button: gradient + shimmer + BoltIcon (same as SEND). Cancel: ghost border

---

## 12. Modals

### Modal Wrapper
- Overlay: absolute inset, rgba(0,0,0,0.6), backdrop-filter: blur(4px), z-index 200
- Card: bg-elevated, 1px border, border-radius 14px, max-width 480px, width 90%, max-height 80vh, overflow auto
- Entry animation: modalIn 0.25s ease
- Close: overlay click or Escape key

### Session Launcher
- Header: "Start a Session" Orbitron 20px 700 + BoltIcon 20px
- Goal input: full width, bg-input, 1px purple border 40%, border-radius 8px, Source Sans 3 16px, box-shadow `0 0 8px purple15`
- Session types (4 cards): Rajdhani 700 18px name, Source Sans 3 15px desc, RoleTag pills
- Types: Code Review, Debate, Design Critique, Planning
- Custom session: "Design a session" section with text input
- Launch button: gradient + shimmer

### Schedule Modal
- Header: "SCHEDULE MESSAGE" Orbitron 20px 700
- Textarea for message, date/time picker, send button
