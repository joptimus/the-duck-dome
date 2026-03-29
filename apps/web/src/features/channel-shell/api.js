import { mockAgentsByChannelId, mockChannels } from "./mockData";

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
