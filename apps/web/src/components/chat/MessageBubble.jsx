import { useEffect, useRef, useState } from 'react';
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { agentMeta } from '../../constants/agents';
import { AgentLogo, BoltIcon } from '../icons';
import { StatusTag } from '../primitives';
import { MessageToolbar } from './MessageToolbar';
import styles from './MessageBubble.module.css';

const MENTION_PATTERN = /(^|[\s(])(@[a-z0-9_-]+)/gi;
const INLINE_CODE_PATTERN = /(`[^`]+`)/g;

function normalizeDisplayText(value) {
  if (typeof value !== 'string' || value.length === 0) return value;
  return value;
}

function splitTextIntoMentionNodes(value) {
  const nodes = [];
  let lastIndex = 0;

  value.replaceAll(MENTION_PATTERN, (match, prefix, mention, offset) => {
    if (offset > lastIndex) {
      nodes.push({ type: 'text', value: value.slice(lastIndex, offset) });
    }
    if (prefix) {
      nodes.push({ type: 'text', value: prefix });
    }
    nodes.push({
      type: 'link',
      url: `mention:${mention.slice(1).toLowerCase()}`,
      children: [{ type: 'text', value: mention }],
    });
    lastIndex = offset + match.length;
    return match;
  });

  if (lastIndex < value.length) {
    nodes.push({ type: 'text', value: value.slice(lastIndex) });
  }

  return nodes.length > 0 ? nodes : [{ type: 'text', value }];
}

function transformMentionNodes(node) {
  if (!node || typeof node !== 'object') return;
  if (!Array.isArray(node.children)) return;

  const nextChildren = [];
  for (const child of node.children) {
    if (child?.type === 'text' && typeof child.value === 'string' && child.value.includes('@')) {
      nextChildren.push(...splitTextIntoMentionNodes(child.value));
      continue;
    }
    transformMentionNodes(child);
    nextChildren.push(child);
  }
  node.children = nextChildren;
}

function remarkMentions() {
  return (tree) => {
    transformMentionNodes(tree);
  };
}

function splitDetailSegments(detail) {
  return String(detail || '')
    .split(INLINE_CODE_PATTERN)
    .filter(Boolean)
    .map((segment) => ({
      value: segment,
      isCode: segment.startsWith('`') && segment.endsWith('`'),
    }));
}

function RoleDropdown({ onClose }) {
  const roles = ['None', 'Planner', 'Designer', 'Architect', 'Builder', 'Reviewer', 'Researcher', 'Red Team', 'Wry', 'Unhinged', 'Hype'];
  return (
    <div className={styles.roleDropdown}>
      <div className={styles.roleGrid}>
        {roles.map((role) => (
          <button
            key={role}
            type="button"
            className={`${styles.rolePill} ${role === 'None' ? styles.rolePillActive : ''}`}
            onClick={onClose}
          >
            {role}
          </button>
        ))}
      </div>
      <input className={styles.roleInput} placeholder="Custom..." />
    </div>
  );
}

export function MessageBubble({ message, index = 0 }) {
  const [hovered, setHovered] = useState(false);
  const [roleOpen, setRoleOpen] = useState(false);
  const rowRef = useRef(null);

  const agentKey = String(message.agent || message.sender || 'user').toLowerCase();
  const isUser = agentKey === 'user' || agentKey === 'human' || !agentMeta[agentKey];
  const meta = isUser ? agentMeta.user : agentMeta[agentKey];
  const displayName = isUser ? 'You' : meta?.label || String(message.sender || message.agent || '');
  const normalizedText = normalizeDisplayText(message.content || message.text || '');
  const timestamp = message.time || message.timestamp || '--';
  const details = Array.isArray(message.details) ? message.details : [];
  const showControls = !isUser && (hovered || roleOpen);

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
      ref={rowRef}
      className={`${styles.row} ${isUser ? styles.rowUser : ''}`}
      style={{ animation: `fadeUp 0.3s ease ${index * 0.06}s both` }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => {
        if (!roleOpen) {
          setHovered(false);
        }
      }}
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
        }}
      >
        <div className={`${styles.header} ${isUser ? styles.headerUser : ''}`}>
          {!isUser ? (
            <>
              <span className={styles.name} style={{ color: meta?.color }}>{displayName}</span>
              <StatusTag status={message.status} />
              <span className={styles.timestamp}>{timestamp}</span>
              {showControls && (
                <div className={styles.roleWrap}>
                  <button
                    type="button"
                    className={`${styles.roleButton} ${roleOpen ? styles.roleButtonOpen : ''}`}
                    onClick={() => setRoleOpen((value) => !value)}
                  >
                    choose a role
                  </button>
                  {roleOpen && <RoleDropdown onClose={() => setRoleOpen(false)} />}
                </div>
              )}
            </>
          ) : (
            <span className={styles.timestamp}>{timestamp}</span>
          )}
        </div>

        <div className={styles.body}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkMentions]}
            urlTransform={(url) => (typeof url === 'string' && url.startsWith('mention:') ? url : defaultUrlTransform(url))}
            components={{
              a: ({ href, children, ...props }) => {
                if (typeof href === 'string' && href.startsWith('mention:')) {
                  return (
                    <span {...props} className={styles.mention}>
                      {children}
                    </span>
                  );
                }
                return <a href={href} {...props} target="_blank" rel="noreferrer" className={styles.link} />;
              },
              code: ({ inline, className, children, ...props }) =>
                inline ? (
                  <code {...props} className={styles.inlineCode}>{children}</code>
                ) : (
                  <code {...props} className={`${styles.codeBlock} ${className || ''}`.trim()}>{children}</code>
                ),
              pre: ({ children }) => <pre className={styles.pre}>{children}</pre>,
              p: ({ children }) => <p className={styles.paragraph}>{children}</p>,
              ul: ({ children }) => <ul className={styles.list}>{children}</ul>,
              ol: ({ children }) => <ol className={styles.list}>{children}</ol>,
              blockquote: ({ children }) => <blockquote className={styles.blockquote}>{children}</blockquote>,
            }}
          >
            {normalizedText}
          </ReactMarkdown>
        </div>

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

        {!isUser && (
          <MessageToolbar
            visible={showControls}
            roleOpen={roleOpen}
            agentColor={meta?.color || 'var(--text-muted)'}
            messageText={normalizedText}
          />
        )}
      </div>
    </div>
  );
}

