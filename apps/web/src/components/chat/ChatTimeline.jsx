import { useEffect, useRef } from 'react';
import { MessageBubble } from './MessageBubble';
import { SystemMessage } from './SystemMessage';
import { ToolApprovalCard } from './ToolApprovalCard';
import { DateDivider } from './DateDivider';
import styles from './ChatTimeline.module.css';

export function ChatTimeline({
  messages = [],
  channelName,
  onApprove,
  onDeny,
  onReply,
  onDelete,
  onPin,
  onConvertToJob,
  onReplyJump,
  pinnedMessageIds = [],
}) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  if (messages.length === 0) {
    return (
      <div className={styles.timeline}>
        <div className={styles.empty}>No messages yet in #{channelName || 'channel'}.</div>
      </div>
    );
  }

  return (
    <div className={styles.timeline}>
      {messages.map((msg, idx) => {
        if (msg.sender_type === 'date_divider') {
          return <DateDivider key={msg.id} label={msg.text} />;
        }
        if (msg.type === 'tool_approval' || msg.sender_type === 'tool_approval') {
          return (
            <ToolApprovalCard
              key={msg.id}
              msg={msg}
              idx={idx}
              onApprove={() => onApprove?.(msg.id)}
              onDeny={() => onDeny?.(msg.id)}
            />
          );
        }
        if (msg.type === 'system' || msg.sender_type === 'system') {
          return <SystemMessage key={msg.id} msg={msg} idx={idx} />;
        }
        return (
          <MessageBubble
            key={msg.id}
            message={msg}
            index={idx}
            onReply={onReply}
            onDelete={onDelete}
            onPin={onPin}
            onConvertToJob={onConvertToJob}
            onReplyJump={onReplyJump}
            isPinned={pinnedMessageIds.includes(msg.id)}
          />
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
