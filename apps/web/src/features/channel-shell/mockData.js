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
    {
      id: "ch-general:claude",
      channel_id: "ch-general",
      agent_type: "claude",
      name: "Claude",
      status: AgentPresence.IDLE,
      last_heartbeat: now(),
      open_trigger_count: 0,
    },
    {
      id: "ch-general:codex",
      channel_id: "ch-general",
      agent_type: "codex",
      name: "Codex",
      status: AgentPresence.WORKING,
      current_task: "Reviewing mention in channel",
      last_heartbeat: now(),
      last_response_time: now(),
      open_trigger_count: 1,
    },
    {
      id: "ch-general:gemini",
      channel_id: "ch-general",
      agent_type: "gemini",
      name: "Gemini",
      status: AgentPresence.OFFLINE,
      last_heartbeat: "--",
      last_error: "Runner unavailable",
      open_trigger_count: 0,
    },
  ],
  "ch-duckdome": [
    {
      id: "ch-duckdome:claude",
      channel_id: "ch-duckdome",
      agent_type: "claude",
      name: "Claude",
      status: AgentPresence.WORKING,
      current_task: "Preparing implementation notes",
      last_heartbeat: now(),
      last_response_time: now(),
      open_trigger_count: 2,
    },
    {
      id: "ch-duckdome:codex",
      channel_id: "ch-duckdome",
      agent_type: "codex",
      name: "Codex",
      status: AgentPresence.IDLE,
      last_heartbeat: now(),
      last_response_time: now(),
      open_trigger_count: 1,
    },
    {
      id: "ch-duckdome:gemini",
      channel_id: "ch-duckdome",
      agent_type: "gemini",
      name: "Gemini",
      status: AgentPresence.IDLE,
      last_heartbeat: now(),
      last_response_time: now(),
      open_trigger_count: 0,
    },
  ],
};

export const mockTriggersByChannelId = {
  "ch-general": [
    { id: "tg-1", channel_id: "ch-general", target: "codex", state: "pending" },
    { id: "tg-2", channel_id: "ch-general", target: "codex", state: "claimed" },
  ],
  "ch-duckdome": [
    { id: "tg-3", channel_id: "ch-duckdome", target: "claude", state: "pending" },
    { id: "tg-4", channel_id: "ch-duckdome", target: "claude", state: "claimed" },
    { id: "tg-5", channel_id: "ch-duckdome", target: "codex", state: "claimed" },
    { id: "tg-6", channel_id: "ch-duckdome", target: "gemini", state: "failed" },
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
