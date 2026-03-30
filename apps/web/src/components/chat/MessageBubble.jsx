import { useState } from 'react';
import { MessageToolbar } from './MessageToolbar';
import styles from './MessageBubble.module.css';

const AGENT_META = {
  claude: { color: 'var(--agent-claude)', bg: 'var(--agent-claude-bg)', border: 'var(--agent-claude-border)' },
  codex: { color: 'var(--agent-codex)', bg: 'var(--agent-codex-bg)', border: 'var(--agent-codex-border)' },
  gemini: { color: 'var(--agent-gemini)', bg: 'var(--agent-gemini-bg)', border: 'var(--agent-gemini-border)' },
  kimi: { color: 'var(--agent-kimi)', bg: 'var(--agent-kimi-bg)', border: 'var(--agent-kimi-border)' },
  qwen: { color: 'var(--agent-qwen)', bg: 'var(--agent-qwen-bg)', border: 'var(--agent-qwen-border)' },
  kilo: { color: 'var(--agent-kilo)', bg: 'var(--agent-kilo-bg)', border: 'var(--agent-kilo-border)' },
  minimax: { color: 'var(--agent-minimax)', bg: 'var(--agent-minimax-bg)', border: 'var(--agent-minimax-border)' },
};

function renderTextWithMentions(text) {
  const parts = text.split(/(@\w+)/g);
  return parts.map((part, i) =>
    part.startsWith('@') ? (
      <span key={i} className={styles.mention}>{part}</span>
    ) : (
      part
    )
  );
}

function formatTime(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function MessageBubble({ message, index = 0 }) {
  const [hovered, setHovered] = useState(false);
  const { sender, text, timestamp } = message;
  const isUser = !AGENT_META[sender?.toLowerCase()];
  const agent = AGENT_META[sender?.toLowerCase()];

  const rowClass = `${styles.row} ${isUser ? styles.rowUser : ''}`;
  const bubbleClass = `${styles.bubble} ${isUser ? styles.bubbleUser : styles.bubbleAgent}`;

  const bubbleStyle = agent
    ? { background: agent.bg, borderColor: agent.border }
    : {};

  return (
    <div
      className={rowClass}
      style={{ animationDelay: `${index * 0.03}s` }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {!isUser && (
        <div
          className={styles.avatar}
          style={{
            border: `2px solid ${agent?.color || 'var(--text-muted)'}`,
            color: agent?.color || 'var(--text-muted)',
          }}
        >
          {sender?.[0]?.toUpperCase() || '?'}
        </div>
      )}

      <div className={bubbleClass} style={bubbleStyle}>
        <div className={styles.header}>
          <span className={styles.name} style={{ color: agent?.color || 'var(--text-primary)' }}>
            {sender}
          </span>
          <span className={styles.timestamp}>{formatTime(timestamp)}</span>
        </div>
        <div className={styles.body}>
          {renderTextWithMentions(text)}
        </div>

        {hovered && <MessageToolbar messageId={message.id} />}
      </div>
    </div>
  );
}
