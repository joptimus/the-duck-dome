import { useState } from 'react';
import styles from './ChannelList.module.css';

export function ChannelList({ channels, activeChannel, onSelect, onDelete }) {
  return (
    <div>
      {channels.map((ch) => (
        <ChannelRow
          key={ch.id || ch.name}
          channel={ch}
          active={activeChannel === (ch.id || ch.name)}
          onSelect={() => onSelect(ch.id || ch.name)}
          onDelete={() => onDelete(ch.name)}
        />
      ))}
    </div>
  );
}

function ChannelRow({ channel, active, onSelect, onDelete }) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      className={`${styles.row} ${active ? styles.active : ''}`}
      onClick={onSelect}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {active && <div className={styles.activeBar} />}
      <span className={`${styles.hash} ${active ? styles.hashActive : ''}`}>#</span>
      <span className={`${styles.name} ${active ? styles.nameActive : ''}`}>
        {channel.name}
      </span>
      {channel.unread > 0 && (
        <span className={styles.unreadBadge}>{channel.unread}</span>
      )}
      {hovered && !active && (
        <button
          className={styles.deleteBtn}
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
        >
          &times;
        </button>
      )}
    </div>
  );
}
