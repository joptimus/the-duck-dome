import { Dot } from '../primitives/Dot';
import { agentMeta } from '../../constants/agents';
import styles from './AgentThinkingStrip.module.css';

export function AgentThinkingStrip({ agents }) {
  if (!agents || agents.length === 0) return null;

  return (
    <div className={styles.strip}>
      {agents.map((a) => {
        const meta = agentMeta[a.agent_type];
        if (!meta) return null;
        return (
          <div key={a.agent_type} className={styles.agent}>
            <Dot color={meta.color} size={6} />
            <span className={styles.text}>
              <span style={{ color: meta.color, fontWeight: 500 }}>
                {meta.label}
              </span>{' '}
              is {a.status}...
            </span>
          </div>
        );
      })}
    </div>
  );
}
