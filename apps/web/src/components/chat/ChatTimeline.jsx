import { useRef, useEffect } from 'react';
import { DateDivider } from './DateDivider';
import { SystemMessage } from './SystemMessage';
import { ToolApprovalCard } from './ToolApprovalCard';
import { SessionBanner } from './SessionBanner';
import styles from './ChatTimeline.module.css';

export function ChatTimeline({
  messages,
  session,
  renderMessage, // function(msg, idx) => JSX for chat-type messages (MsgBubble)
  onApprove,
  onDeny,
}) {
  const scrollRef = useRef(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div ref={scrollRef} className={styles.timeline}>
      {/* Session banner */}
      {session && (
        <SessionBanner
          sessionId={session.id}
          agentCount={session.agentCount}
        />
      )}

      {/* Message dispatch */}
      {messages.map((msg, i) => {
        if (msg.type === 'date_divider') {
          return <DateDivider key={i} label={msg.label} />;
        }
        if (msg.type === 'system') {
          return <SystemMessage key={i} msg={msg} idx={i} />;
        }
        if (msg.type === 'tool_approval') {
          return (
            <ToolApprovalCard
              key={msg.id || i}
              msg={msg}
              idx={i}
              onApprove={() => onApprove?.(msg)}
              onDeny={() => onDeny?.(msg)}
            />
          );
        }
        // Default: chat message (MsgBubble from UI-8a)
        return renderMessage(msg, i);
      })}
    </div>
  );
}
