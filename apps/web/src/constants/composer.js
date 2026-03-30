export const slashCommands = [
  {
    cmd: "/artchallenge",
    desc: "SVG art challenge — all agents create artwork (optional theme)",
  },
  { cmd: "/hatmaking", desc: "All agents design a hat to wear on their avatar" },
  {
    cmd: "/roastreview",
    desc: "Get all agents to review and roast each other's work",
  },
  { cmd: "/poetry haiku", desc: "Agents write a haiku about the codebase" },
  { cmd: "/poetry limerick", desc: "Agents write a limerick about the codebase" },
  { cmd: "/poetry sonnet", desc: "Agents write a sonnet about the codebase" },
  {
    cmd: "/summary",
    desc: "Summarize recent messages — tag an agent (e.g. /summary @claude)",
  },
  { cmd: "/continue", desc: "Resume after loop guard pauses" },
  { cmd: "/clear", desc: "Clear messages in current channel" },
  { cmd: "/session start", desc: "Launch a new collaborative session" },
  { cmd: "/session end", desc: "End the current active session" },
  { cmd: "/jobs list", desc: "List all jobs in the current channel" },
  { cmd: "/rules remind", desc: "Remind all agents of the current rules" },
];

