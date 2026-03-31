import { mockAgentsByChannelId, mockChannels, mockTriggersByChannelId } from "./mockData";

const API_BASE = (import.meta.env.VITE_API_BASE ?? "http://localhost:8000").replace(/\/$/, "");

async function request(path, options) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, options);
  } catch (error) {
    const networkError = error instanceof Error ? error : new Error("Network request failed");
    networkError.isNetworkError = true;
    throw networkError;
  }

  if (!response.ok) {
    const bodyText = await response.text();
    const httpError = new Error(`Request failed: ${response.status}${bodyText ? ` - ${bodyText}` : ""}`);
    httpError.status = response.status;
    httpError.body = bodyText;
    httpError.isNetworkError = false;
    throw httpError;
  }

  return response.json();
}

export async function getChannels() {
  try {
    return await request("/api/channels");
  } catch (error) {
    if (!error?.isNetworkError) throw error;
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
  } catch (error) {
    if (!error?.isNetworkError) throw error;
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
  } catch (error) {
    if (!error?.isNetworkError) throw error;
    return mockChannels.find((channel) => channel.id === channelId) || null;
  }
}

export async function getChannelAgents(channelId) {
  try {
    return await request(`/api/channels/${encodeURIComponent(channelId)}/agents`);
  } catch (error) {
    if (!error?.isNetworkError) throw error;
    return mockAgentsByChannelId[channelId] || [];
  }
}

export async function addChannelAgent(channelId, agentType) {
  try {
    return await request(`/api/channels/${encodeURIComponent(channelId)}/agents`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agent_type: agentType }),
    });
  } catch (error) {
    if (!error?.isNetworkError) throw error;
    return {
      id: `${channelId}:${agentType}`,
      channel_id: channelId,
      agent_type: agentType,
      status: "idle",
      last_heartbeat: null,
    };
  }
}

export async function removeChannelAgent(channelId, agentType) {
  return request(`/api/channels/${encodeURIComponent(channelId)}/agents/${encodeURIComponent(agentType)}`, {
    method: "DELETE",
  });
}

export async function registerRuntimeAgent(channelId, agentType) {
  try {
    return await request("/api/agents/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        channel_id: channelId,
        agent_type: agentType,
      }),
    });
  } catch (error) {
    if (!error?.isNetworkError && !(error?.status >= 500)) throw error;
    return {
      id: `${channelId}:${agentType}`,
      channel_id: channelId,
      agent_type: agentType,
      status: "idle",
      __localFallback: true,
    };
  }
}

export async function deregisterRuntimeAgent(channelId, agentType) {
  try {
    return await request("/api/agents/deregister", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        channel_id: channelId,
        agent_type: agentType,
      }),
    });
  } catch (error) {
    if (!error?.isNetworkError && !(error?.status >= 500)) throw error;
    return {
      id: `${channelId}:${agentType}`,
      channel_id: channelId,
      agent_type: agentType,
      status: "offline",
      __localFallback: true,
    };
  }
}

export async function getChannelTriggers(channelId) {
  try {
    return await request(`/api/channels/${encodeURIComponent(channelId)}/triggers`);
  } catch (error) {
    if (error?.isNetworkError) return mockTriggersByChannelId[channelId] || [];
    if (error?.status !== 404) throw error;
  }

  try {
    return await request(`/api/triggers?channel_id=${encodeURIComponent(channelId)}`);
  } catch (error) {
    if (!error?.isNetworkError) throw error;
    return mockTriggersByChannelId[channelId] || [];
  }
}

export async function getChannelMessages(channelId) {
  return request(`/api/messages?channel=${encodeURIComponent(channelId)}`);
}

export async function getPendingToolRequests(channelId) {
  try {
    return await request(`/api/tool_approvals/pending?channel=${encodeURIComponent(channelId)}`);
  } catch (error) {
    if (!error?.isNetworkError) throw error;
    return [];
  }
}

export async function sendChannelMessage({ channelId, text, sender = "human" }) {
  return request("/api/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text,
      channel: channelId,
      sender,
    }),
  });
}

export async function triggerAgent(agentType, sender, text, channelId) {
  return request("/api/wrapper/trigger", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      agent_type: agentType,
      sender,
      text,
      channel: channelId,
    }),
  });
}

export async function approveToolRequest(approvalId, { remember = false } = {}) {
  return request(`/api/tool_approvals/${encodeURIComponent(approvalId)}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resolved_by: "human", remember }),
  });
}

export async function denyToolRequest(approvalId, { remember = false } = {}) {
  return request(`/api/tool_approvals/${encodeURIComponent(approvalId)}/deny`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resolved_by: "human", remember }),
  });
}

export async function getRepos() {
  return request("/api/repos");
}

export async function addRepoSource(path) {
  return request("/api/repos/add", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
}

export async function removeRepoSource(path) {
  return request("/api/repos/remove", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
}
