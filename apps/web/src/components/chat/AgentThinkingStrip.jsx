import { agentMeta } from '../../constants/agents';
import { Dot } from '../primitives/Dot';
import styles from './AgentThinkingStrip.module.css';

export function AgentThinkingStrip({ agents = [], failure }) {
  const workingAgents = agents.filter((a) => a.status === 'working');

  if (workingAgents.length === 0 && !failure) {
    return null;
  }

  return (
    <div className={styles.strip}>
      {workingAgents.map((agent) => {
        const meta = agentMeta[agent.agent_type] || {};
        return (
          <span key={agent.id} className={styles.item}>
            <Dot color={meta.color || 'var(--text-muted)'} size={6} pulse />
            <span className={styles.label} style={{ color: meta.color }}>
              {meta.label || agent.agent_type} is working...
            </span>
          </span>
        );
      })}
      {failure && (
        <span className={styles.error}>
          {(agentMeta[failure.agent]?.label || failure.agent)} failed: {failure.summary}
        </span>
      )}
    </div>
  );
}
