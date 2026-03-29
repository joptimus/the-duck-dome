function statusClass(status) {
  if (status === "working") return "agent-pill agent-pill--working";
  if (status === "online") return "agent-pill agent-pill--online";
  return "agent-pill agent-pill--offline";
}

export default function AgentStatusRow({ agents }) {
  return (
    <section className="agent-row" aria-label="Channel agent status">
      {agents.map((agent) => (
        <article key={agent.id} className={statusClass(agent.status)}>
          <div className="agent-pill__top">
            <strong>{agent.name}</strong>
            <span>{agent.status}</span>
          </div>
          <div className="agent-pill__last">Last activity: {agent.last_activity || "--"}</div>
        </article>
      ))}
    </section>
  );
}
