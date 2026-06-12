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

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

export async function getChannels() {
  return request("/api/channels");
}

export async function createChannel(payload) {
  return request("/api/channels", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteChannel(channelId) {
  return request(`/api/channels/${encodeURIComponent(channelId)}`, {
    method: "DELETE",
  });
}

export async function getChannel(channelId) {
  return request(`/api/channels/${encodeURIComponent(channelId)}`);
}

export async function getChannelAgents(channelId) {
  return request(`/api/channels/${encodeURIComponent(channelId)}/agents`);
}

export async function addChannelAgent(channelId, agentType) {
  return request(`/api/channels/${encodeURIComponent(channelId)}/agents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent_type: agentType }),
  });
}

export async function removeChannelAgent(channelId, agentType) {
  return request(`/api/channels/${encodeURIComponent(channelId)}/agents/${encodeURIComponent(agentType)}`, {
    method: "DELETE",
  });
}

export async function registerRuntimeAgent(channelId, agentType) {
  return request("/api/agents/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      channel_id: channelId,
      agent_type: agentType,
    }),
  });
}

export async function deregisterRuntimeAgent(channelId, agentType) {
  return request("/api/agents/deregister", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      channel_id: channelId,
      agent_type: agentType,
    }),
  });
}

export async function getChannelTriggers(channelId) {
  try {
    return await request(`/api/channels/${encodeURIComponent(channelId)}/triggers`);
  } catch (error) {
    if (error?.status !== 404) throw error;
  }
  return request(`/api/triggers?channel_id=${encodeURIComponent(channelId)}`);
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

export async function sendChannelMessage({ channelId, text, sender = "human", replyTo = null }) {
  return request("/api/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text,
      channel: channelId,
      sender,
      reply_to: replyTo,
    }),
  });
}

export async function deleteChannelMessage(messageId) {
  return request(`/api/messages/${encodeURIComponent(messageId)}`, {
    method: "DELETE",
  });
}

export async function bootChannel(channelId) {
  return request("/api/wrapper/boot-channel", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ channel: channelId }),
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

export async function getJobs(channelId) {
  return request(`/api/jobs?channel=${encodeURIComponent(channelId)}`);
}

export async function createJob(payload) {
  return request("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
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

export async function updateAgentPermissions(agentKey, permissions) {
  const result = await request(`/api/agents/${encodeURIComponent(agentKey)}/permissions`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      agent: agentKey,
      permissions,
    }),
  });
  return result?.permissions ?? result ?? permissions;
}
