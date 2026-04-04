import { Dot } from '../primitives/Dot';
import { BoltIcon } from '../icons/BoltIcon';
import { agentMeta } from '../../constants/agents';
import styles from './SystemMessage.module.css';

// Warning triangle SVG (inline, not in icon library)
function WarningTriangle() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none"
      stroke="var(--warning)" strokeWidth={2}
      strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

export function SystemMessage({ msg, idx = 0 }) {
  const meta = msg.agent ? agentMeta[msg.agent] : null;
  const agentColor = meta?.color || 'var(--text-muted)';
  const isJoin = msg.subtype === 'join';
  const isLeave = msg.subtype === 'leave';
  const isError = msg.subtype === 'error';

  const animStyle = { animation: 'fadeUp 0.45s cubic-bezier(0.4, 0, 0.2, 1) both' };

  // ── Join / Leave ──
  if (isJoin || isLeave) {
    return (
      <div className={styles.joinLeave} style={animStyle}>
        <Dot color={isJoin ? 'var(--success)' : 'var(--text-muted)'} size={5} />
        <span className={styles.agentName} style={{ color: agentColor }}>
          {meta?.label || msg.agent}
        </span>
        <span className={styles.content}>{msg.content}</span>
        <span className={styles.timestamp}>{msg.time}</span>
      </div>
    );
  }

  // ── Error ──
  if (isError) {
    return (
      <div className={styles.error} style={animStyle}>
        <div className={styles.errorIcon}>
          <WarningTriangle />
        </div>
        <div className={styles.errorBody}>
          <span className={styles.errorText}>
            Agent routing for{' '}
            <span style={{ color: agentColor, fontWeight: 500 }}>
              {meta?.label || msg.agent}
            </span>{' '}
            interrupted — auto-recovered. If agents aren&apos;t responding, try
            sending your message again.
          </span>
        </div>
        <span className={styles.errorTimestamp}>{msg.time}</span>
      </div>
    );
  }

  // ── Info (default) ──
  return (
    <div className={styles.info} style={animStyle}>
      <BoltIcon size={11} color="var(--info)" glow={false} />
      <span className={styles.infoText}>{msg.content}</span>
      <span className={styles.timestamp}>{msg.time}</span>
    </div>
  );
}
