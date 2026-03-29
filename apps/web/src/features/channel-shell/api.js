import { mockAgentsByChannelId, mockChannels } from "./mockData";

const API_BASE = "http://localhost:8000";

async function request(path, options) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

export async function getChannels() {
  try {
    return await request("/api/channels");
  } catch (_error) {
    return mockChannels;
  }
}

export async function createChannel(payload) {
  try {
    return await request("/api/channels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (_error) {
    const id = `local-${Date.now()}`;
    return {
      id,
      name: payload.name,
      type: payload.type,
      repo_path: payload.repo_path || null,
      unread_count: 0,
    };
  }
}

export async function getChannel(channelId) {
  try {
    return await request(`/api/channels/${encodeURIComponent(channelId)}`);
  } catch (_error) {
    return mockChannels.find((channel) => channel.id === channelId) || null;
  }
}

export async function getChannelAgents(channelId) {
  try {
    return await request(`/api/channels/${encodeURIComponent(channelId)}/agents`);
  } catch (_error) {
    return mockAgentsByChannelId[channelId] || [];
  }
}
