const TRACKED_AGENTS = ["claude", "codex", "gemini"];

function title(name) {
  return name.slice(0, 1).toUpperCase() + name.slice(1);
}

function statusClass(status) {
  if (status === "error") return "runtime-pill runtime-pill--error";
  if (status === "working") return "runtime-pill runtime-pill--working";
  if (status === "idle") return "runtime-pill runtime-pill--idle";
  return "runtime-pill runtime-pill--offline";
}

function shorten(text, max = 42) {
  if (!text) return "--";
  const value = String(text).trim();
  if (value.length <= max) return value;
  return `${value.slice(0, max - 1)}...`;
}

export default function AgentRuntimeStrip({ agentMap }) {
  return (
    <section className="runtime-strip" aria-label="Channel runtime status">
      {TRACKED_AGENTS.map((agentType) => {
        const agent = agentMap[agentType] || {
          status: "offline",
          open_trigger_count: 0,
        };
        const status = agent.last_error ? "error" : agent.status;

        return (
          <article key={agentType} className={statusClass(status)}>
            <div className="runtime-pill__top">
              <strong>{title(agentType)}</strong>
              <span>{status}</span>
            </div>
            <div className="runtime-pill__line">Last seen: {agent.last_heartbeat || "--"}</div>
            <div className="runtime-pill__line">Current task: {shorten(agent.current_task)}</div>
            <div className="runtime-pill__line">Last run: {agent.last_response_time || "--"}</div>
            <div className="runtime-pill__line">Open triggers: {agent.open_trigger_count || 0}</div>
            {agent.last_error ? <div className="runtime-pill__error">Error: {agent.last_error}</div> : null}
          </article>
        );
      })}
    </section>
  );
}
