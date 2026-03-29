import { AgentPresence, ChannelType } from "./types";

export const mockChannels = [
  { id: "ch-general", name: "general", type: ChannelType.GENERAL, unread_count: 0 },
  {
    id: "ch-duckdome",
    name: "duckdome-ui",
    type: ChannelType.REPO,
    repo_path: "./the-duck-dome",
    unread_count: 2,
  },
];

const now = () => new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

export const mockAgentsByChannelId = {
  "ch-general": [
    { id: "claude", name: "Claude", status: AgentPresence.ONLINE, last_activity: now() },
    { id: "codex", name: "Codex", status: AgentPresence.WORKING, last_activity: now() },
    { id: "gemini", name: "Gemini", status: AgentPresence.OFFLINE, last_activity: "--" },
  ],
  "ch-duckdome": [
    { id: "claude", name: "Claude", status: AgentPresence.WORKING, last_activity: now() },
    { id: "codex", name: "Codex", status: AgentPresence.ONLINE, last_activity: now() },
    { id: "gemini", name: "Gemini", status: AgentPresence.ONLINE, last_activity: now() },
  ],
};

export const mockMessagesByChannelId = {
  "ch-general": [
    { id: "m1", sender: "system", text: "Welcome to DuckDome channels.", time: "09:00" },
  ],
  "ch-duckdome": [
    { id: "m2", sender: "James", text: "@claude check the channel shell layout", time: "09:15" },
    { id: "m3", sender: "Claude", text: "I can see the repo-bound channel context.", time: "09:17" },
  ],
};
