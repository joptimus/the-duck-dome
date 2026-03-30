import { useState } from 'react';
import styles from './MessageToolbar.module.css';

export function MessageToolbar({ messageId }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className={styles.toolbar}>
      <button className={styles.btn} title="Reply">↩</button>
      <button className={styles.btn} title="Pin">📌</button>
      <button
        className={`${styles.btn} ${copied ? styles.copied : ''}`}
        title="Copy"
        onClick={handleCopy}
      >
        {copied ? '✓' : '📋'}
      </button>
      {copied && <div className={styles.tooltip}>Copied!</div>}
      <button className={styles.btn} title="Convert to job">📋</button>
      <div className={styles.divider} />
      <button className={`${styles.btn} ${styles.btnDelete}`} title="Delete">🗑</button>
    </div>
  );
}
