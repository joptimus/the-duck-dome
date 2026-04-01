import { useEffect, useState } from 'react';
import {
  BoltIcon,
  CheckIcon,
  CopyIcon,
  PinIcon,
  ReplyIcon,
  TrashIcon,
} from '../icons';
import styles from './MessageToolbar.module.css';

export function MessageToolbar({
  visible,
  roleOpen = false,
  agentColor,
  messageText = '',
  pinned = false,
  onCopy,
  onReply,
  onPin,
  onConvertToJob,
  onDelete,
}) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return undefined;
    const timeoutId = window.setTimeout(() => setCopied(false), 1800);
    return () => window.clearTimeout(timeoutId);
  }, [copied]);

  const isVisible = visible || roleOpen;
  const borderTopColor = typeof agentColor === 'string' && agentColor.startsWith('var(')
    ? agentColor
    : `${agentColor}2e`;

  const handleCopy = async () => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(messageText);
      }
      onCopy?.();
      setCopied(true);
    } catch {
      // Ignore clipboard failures for now.
    }
  };

  return (
    <div
      className={`${styles.toolbar} ${isVisible ? styles.toolbarVisible : ''}`}
      style={{ borderTopColor }}
    >
      <button className={styles.btn} title="Reply" type="button" aria-label="Reply" onClick={onReply}>
        <ReplyIcon size={13} color="currentColor" />
      </button>
      <button
        className={`${styles.btn} ${pinned ? styles.pinned : ''}`}
        title={pinned ? 'Unpin' : 'Pin'}
        type="button"
        aria-label={pinned ? 'Unpin' : 'Pin'}
        onClick={onPin}
      >
        <PinIcon size={13} color="currentColor" />
      </button>
      <button
        className={`${styles.btn} ${copied ? styles.copied : ''}`}
        title="Copy"
        type="button"
        aria-label="Copy"
        onClick={handleCopy}
      >
        {copied ? <CheckIcon size={13} color="currentColor" /> : <CopyIcon size={13} color="currentColor" />}
        {copied && <div className={styles.tooltip}>Copied!</div>}
      </button>
      <button className={styles.btn} title="Convert to Job" type="button" aria-label="Convert to Job" onClick={onConvertToJob}>
        <BoltIcon size={11} color="currentColor" glow={false} />
      </button>
      <div className={styles.spacer} />
      <button className={`${styles.btn} ${styles.btnDelete}`} title="Delete" type="button" aria-label="Delete" onClick={onDelete}>
        <TrashIcon size={13} color="currentColor" />
      </button>
    </div>
  );
}
