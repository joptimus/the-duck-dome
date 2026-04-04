const API_BASE = (import.meta.env.VITE_API_BASE ?? "http://localhost:8000").replace(/\/$/, "");

export async function fetchSettings() {
  try {
    const response = await fetch(`${API_BASE}/api/settings`);
    if (response.ok) return response.json();
  } catch {
    /* ignore */
  }
  return { show_agent_windows: false };
}

export async function patchSettings(patch) {
  const response = await fetch(`${API_BASE}/api/settings`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!response.ok) {
    throw new Error(`PATCH /api/settings failed: ${response.status}`);
  }
  return response.json();
}
