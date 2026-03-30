import { BoltIcon } from '../icons/BoltIcon';
import styles from './SessionBanner.module.css';

export function SessionBanner({ sessionId = 'DD-0424-A', agentCount = 3 }) {
  return (
    <div className={styles.banner}>
      <div className={styles.lineLeft} />
      <div className={styles.pill}>
        <BoltIcon size={12} color="var(--success)" />
        <span className={styles.label}>SESSION ACTIVE</span>
        <span className={styles.divider} />
        <span className={styles.sessionId}>{sessionId}</span>
        <span className={styles.divider} />
        <span className={styles.agentCount}>{agentCount} AGENTS</span>
      </div>
      <div className={styles.lineRight} />
    </div>
  );
}
