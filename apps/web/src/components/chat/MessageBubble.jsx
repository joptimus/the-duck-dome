import { useEffect, useRef, useState } from 'react';
import { agentMeta } from '../../constants/agents';
import { AgentLogo, BoltIcon } from '../icons';
import { StatusTag } from '../primitives';
import { MessageContent } from './MessageContent';
import { MessageToolbar } from './MessageToolbar';
import styles from './MessageBubble.module.css';

const INLINE_CODE_PATTERN = /(`[^`]+`)/g;
const ROLE_OPTIONS = ['None', 'Planner', 'Designer', 'Architect', 'Builder', 'Reviewer', 'Researcher', 'Red Team', 'Wry', 'Unhinged', 'Hype'];
const UNKNOWN_AGENT_META = {
  color: 'var(--text-muted)',
  label: 'Unknown agent',
  bg: 'rgba(255,255,255,0.03)',
  border: 'rgba(255,255,255,0.14)',
};

function splitDetailSegments(detail) {
  return String(detail || '')
    .split(INLINE_CODE_PATTERN)
    .filter(Boolean)
    .map((segment) => ({
      value: segment,
      isCode: segment.startsWith('`') && segment.endsWith('`'),
    }));
}

function RoleDropdown({ selectedRole = '', onSelect, onClose }) {
  const [customRole, setCustomRole] = useState('');

  function handleSelect(role) {
    const nextRole = role === 'None' ? '' : role;
    onSelect?.(nextRole);
    onClose?.();
  }

  function handleCustomCommit() {
    const nextRole = customRole.trim();
    if (!nextRole) return;
    onSelect?.(nextRole);
    onClose?.();
  }

  return (
    <div className={styles.roleDropdown}>
      <div className={styles.roleGrid}>
        {ROLE_OPTIONS.map((role) => {
          const isActive = (role === 'None' && !selectedRole) || role === selectedRole;
          return (
          <button
            key={role}
            type="button"
            className={`${styles.rolePill} ${isActive ? styles.rolePillActive : ''}`}
            onClick={() => handleSelect(role)}
          >
            {role}
          </button>
          );
        })}
      </div>
      <input
        className={styles.roleInput}
        placeholder="Custom..."
        value={customRole}
        onChange={(event) => setCustomRole(event.target.value)}
        onBlur={handleCustomCommit}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            handleCustomCommit();
          }
        }}
      />
    </div>
  );
}

export function MessageBubble({
  message,
  index = 0,
  onReply,
  onDelete,
  onPin,
  onConvertToJob,
  onReplyJump,
  isPinned = false,
}) {
  const [hovered, setHovered] = useState(false);
  const [roleOpen, setRoleOpen] = useState(false);
  const [selectedRole, setSelectedRole] = useState('');
  const rowRef = useRef(null);

  const agentKey = String(message.agent || message.sender || 'user').toLowerCase();
  const isUser = agentKey === 'user' || agentKey === 'human' || agentKey === 'you';
  const isUnknownAgent = !isUser && !agentMeta[agentKey];
  const meta = isUser ? agentMeta.user : agentMeta[agentKey] || UNKNOWN_AGENT_META;
  const displayName = isUser
    ? 'You'
    : isUnknownAgent
      ? String(message.sender || message.agent || UNKNOWN_AGENT_META.label)
      : meta?.label || String(message.sender || message.agent || '');
  const normalizedText = message.content || message.text || '';
  const timestamp = message.time || message.timestamp || '--';
  const details = Array.isArray(message.details) ? message.details : [];
  const showControls = hovered || roleOpen;

  useEffect(() => {
    if (!isUnknownAgent || import.meta.env.PROD) return;
    // Unknown agent messages should stay visible instead of silently rendering as user messages.
    console.warn('Missing agent metadata for message bubble agent', { agentKey, message });
  }, [agentKey, isUnknownAgent, message]);

  useEffect(() => {
    if (!roleOpen) return undefined;

    function handlePointerDown(event) {
      if (!rowRef.current?.contains(event.target)) {
        setRoleOpen(false);
      }
    }

    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, [roleOpen]);

  return (
    <div
      id={`message-${message.id}`}
      ref={rowRef}
      className={`${styles.row} ${isUser ? styles.rowUser : ''}`}
      style={{ animation: 'fadeUp 0.45s cubic-bezier(0.4, 0, 0.2, 1) both' }}
    >
      {!isUser && (
        <div
          className={styles.avatar}
          style={{
            background: `${meta.color}26`,
            borderColor: `${meta.color}80`,
          }}
        >
          <AgentLogo agent={agentKey} size={18} />
        </div>
      )}

      <div
        className={`${styles.bubble} ${isUser ? styles.bubbleUser : styles.bubbleAgent}`}
        style={{
          background: meta?.bg,
          borderColor: hovered || roleOpen ? `${meta?.color}66` : meta?.border,
          boxShadow: hovered || roleOpen ? `0 0 12px ${meta?.color}14` : 'none',
        }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => {
          if (!roleOpen) {
            setHovered(false);
          }
        }}
      >
        <div className={`${styles.header} ${isUser ? styles.headerUser : ''}`}>
          {!isUser ? (
            <>
              <span className={styles.name} style={{ color: meta?.color }}>{displayName}</span>
              <StatusTag status={message.status} />
              <span className={styles.timestamp}>{timestamp}</span>
              {!isUser && showControls && (
                <div className={styles.roleWrap}>
                  <button
                    type="button"
                    className={`${styles.roleButton} ${roleOpen ? styles.roleButtonOpen : ''}`}
                    onClick={() => setRoleOpen((value) => !value)}
                  >
                    {selectedRole || 'choose a role'}
                  </button>
                  {roleOpen && (
                    <RoleDropdown
                      selectedRole={selectedRole}
                      onSelect={setSelectedRole}
                      onClose={() => setRoleOpen(false)}
                    />
                  )}
                </div>
              )}
            </>
          ) : (
            <span className={styles.timestamp}>{timestamp}</span>
          )}
        </div>

        <MessageContent
          text={normalizedText}
          replyPreview={message.reply_preview || null}
          onReplyClick={onReplyJump}
        />

        {!isUser && details.length > 0 && (
          <div className={styles.details}>
            <div className={styles.detailsDivider} style={{ background: `${meta.color}2e` }} />
            <div className={styles.detailsLabel} style={{ color: meta.color }}>
              <BoltIcon size={9} color={meta.color} glow={false} />
              <span>Changes:</span>
            </div>
            <div className={styles.detailsList}>
              {details.map((detail, detailIndex) => (
                <div key={`${message.id || index}-detail-${detailIndex}`} className={styles.detailItem}>
                  <span className={styles.detailBullet} style={{ background: `${meta.color}99` }} />
                  <span className={styles.detailText}>
                    {splitDetailSegments(detail).map((segment, segmentIndex) => (
                      segment.isCode ? (
                        <code key={segmentIndex} className={styles.detailCode}>{segment.value.slice(1, -1)}</code>
                      ) : (
                        <span key={segmentIndex}>{segment.value}</span>
                      )
                    ))}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        <MessageToolbar
          visible={showControls}
          roleOpen={roleOpen}
          agentColor={meta?.color || 'var(--text-muted)'}
          messageText={normalizedText}
          pinned={isPinned}
          onReply={() => onReply?.(message)}
          onPin={() => onPin?.(message)}
          onConvertToJob={() => onConvertToJob?.(message)}
          onDelete={() => onDelete?.(message)}
        />
      </div>
    </div>
  );
}
