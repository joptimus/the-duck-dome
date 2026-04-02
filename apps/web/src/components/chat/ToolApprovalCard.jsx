import { useState } from 'react';
import { AgentLogo } from '../icons/AgentLogo';
import {
  ShieldIcon, ShieldCheckIcon, ShieldXIcon, TerminalIcon,
  CheckIcon, XIcon, EyeIcon,
} from '../icons/Icons';
import { agentMeta } from '../../constants/agents';
import styles from './ToolApprovalCard.module.css';

const STATE_COLORS = {
  pending: 'var(--warning)',
  approved: 'var(--success)',
  denied: 'var(--error)',
};

const STATE_LABELS = {
  pending: 'AWAITING APPROVAL',
  approved: 'APPROVED',
  denied: 'DENIED',
};

function ShieldByState({ status, size = 16, color }) {
  if (status === 'approved') return <ShieldCheckIcon size={size} color={color} />;
  if (status === 'denied') return <ShieldXIcon size={size} color={color} />;
  return <ShieldIcon size={size} color={color} />;
}

export function ToolApprovalCard({ msg, idx = 0, onApprove, onDeny }) {
  const meta = agentMeta[msg.agent] || agentMeta.claude;
  const isPending = msg.status === 'pending';
  const borderColor = STATE_COLORS[msg.status] || STATE_COLORS.pending;
  const statusLabel = STATE_LABELS[msg.status] || STATE_LABELS.pending;
  const [showPolicy, setShowPolicy] = useState(false);

  return (
    <div
      className={styles.wrapper}
      style={{ animation: 'fadeUp 0.45s cubic-bezier(0.4, 0, 0.2, 1) both' }}
    >
      {/* Avatar */}
      <div className={styles.avatarCol}>
        <div
          className={styles.avatar}
          style={{
            background: `${meta.color}15`,
            borderColor: `${meta.color}50`,
          }}
        >
          <AgentLogo agent={msg.agent} size={18} />
        </div>
      </div>

      {/* Card */}
      <div
        className={styles.card}
        style={{
          background: `${borderColor}06`,
          borderColor: `${borderColor}30`,
        }}
      >
        {/* Top accent bar */}
        <div
          className={styles.accentBar}
          style={{
            background: borderColor,
            opacity: isPending ? 1 : 0.4,
          }}
        />

        {/* Header */}
        <div className={styles.header}>
          <ShieldByState status={msg.status} size={16} color={borderColor} />
          <span className={styles.agentName} style={{ color: meta.color }}>
            {meta.label}
          </span>
          <span
            className={styles.statusBadge}
            style={{
              color: borderColor,
              background: `${borderColor}15`,
              borderColor: `${borderColor}25`,
            }}
          >
            {statusLabel}
          </span>
          <span className={styles.time}>{msg.time}</span>
          {!isPending && msg.resolvedAt && (
            <span className={styles.time}>{msg.resolvedAt}</span>
          )}
        </div>

        {/* Tool + Command */}
        <div className={styles.commandSection}>
          <div className={styles.toolRow}>
            <TerminalIcon size={12} color="var(--text-muted)" />
            <span className={styles.toolName}>{msg.tool}</span>
            {msg.diff && <span className={styles.diff}>{msg.diff}</span>}
          </div>
          <div className={styles.commandBlock}>
            <span className={styles.commandPrefix}>$ </span>
            {msg.command}
          </div>
        </div>

        {/* Reason */}
        <div className={styles.reason}>{msg.reason}</div>

        {/* Actions -- pending only */}
        {isPending && (
          <div className={styles.actions}>
            <div className={styles.mainButtons}>
              <button className={styles.approveBtn} onClick={onApprove}>
                <CheckIcon size={13} color="var(--success)" />
                APPROVE
              </button>
              <button className={styles.denyBtn} onClick={onDeny}>
                <XIcon size={12} color="var(--error)" />
                DENY
              </button>
            </div>
            <div className={styles.secondaryButtons}>
              <button
                className={`${styles.ghostBtn} ${showPolicy ? styles.ghostBtnActive : ''}`}
                onClick={() => setShowPolicy(!showPolicy)}
              >
                <ShieldCheckIcon size={11} color="currentColor" />
                Always approve this tool
              </button>
              <button className={styles.ghostBtn}>
                <EyeIcon size={11} color="currentColor" />
                View context
              </button>
            </div>

            {/* Auto-approve policy dropdown */}
            {showPolicy && (
              <div className={styles.policyDropdown}>
                <div className={styles.policyHeader}>AUTO-APPROVE POLICY</div>
                {[
                  {
                    label: `Always approve ${msg.tool} for ${meta.label}`,
                    desc: `${meta.label} can run ${msg.tool} without asking`,
                  },
                  {
                    label: 'Always approve this exact command',
                    desc: 'Only this specific invocation is pre-approved',
                  },
                  {
                    label: `Approve all tools for ${meta.label}`,
                    desc: 'This agent runs unrestricted — use with caution',
                  },
                ].map((p, i) => (
                  <div key={i} className={styles.policyRow}>
                    <div className={styles.policyLabel}>{p.label}</div>
                    <div className={styles.policyDesc}>{p.desc}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
