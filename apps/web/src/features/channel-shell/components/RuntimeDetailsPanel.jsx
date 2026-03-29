export default function RuntimeDetailsPanel({ channelId, agents, error }) {
  return (
    <section className="runtime-panel" aria-label="Runtime details">
      <h3>Runtime Details</h3>
      {error ? <div className="runtime-panel__error">Runtime unavailable: {error}</div> : null}
      {!error && agents.length === 0 ? (
        <div className="runtime-panel__empty">No agents in this channel yet.</div>
      ) : null}
      {!error && agents.length > 0 ? (
        <div className="runtime-panel__table-wrap">
          <table className="runtime-panel__table">
            <thead>
              <tr>
                <th>Agent</th>
                <th>Instance ID</th>
                <th>Channel ID</th>
                <th>Current task</th>
                <th>Last response</th>
                <th>Open triggers</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => (
                <tr key={agent.id}>
                  <td>{agent.agent_type}</td>
                  <td>{agent.id}</td>
                  <td>{agent.channel_id || channelId}</td>
                  <td>{agent.current_task || "--"}</td>
                  <td>{agent.last_response_time || "--"}</td>
                  <td>{agent.open_trigger_count || 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
