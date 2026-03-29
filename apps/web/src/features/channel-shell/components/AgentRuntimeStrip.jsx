const TRACKED_AGENTS = ["claude", "codex", "gemini"];

function title(name) {
  return name.slice(0, 1).toUpperCase() + name.slice(1);
}

function statusClass(status) {
  if (status === "working") return "runtime-pill runtime-pill--working";
  if (status === "idle") return "runtime-pill runtime-pill--idle";
  return "runtime-pill runtime-pill--offline";
}

export default function AgentRuntimeStrip({ agentMap }) {
  return (
    <section className="runtime-strip" aria-label="Channel runtime status">
      {TRACKED_AGENTS.map((agentType) => {
        const agent = agentMap[agentType] || {
          status: "offline",
          open_trigger_count: 0,
        };

        return (
          <article key={agentType} className={statusClass(agent.status)}>
            <div className="runtime-pill__top">
              <strong>{title(agentType)}</strong>
              <span>{agent.status}</span>
            </div>
            <div className="runtime-pill__line">Last seen: {agent.last_heartbeat || "--"}</div>
            <div className="runtime-pill__line">Open triggers: {agent.open_trigger_count || 0}</div>
            {agent.last_error ? <div className="runtime-pill__error">Error: {agent.last_error}</div> : null}
          </article>
        );
      })}
    </section>
  );
}
