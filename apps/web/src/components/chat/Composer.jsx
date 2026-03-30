import { useState } from 'react';
import styles from './Composer.module.css';

export function Composer({ onSend, channelName, disabled = false }) {
  const [draft, setDraft] = useState('');

  const submit = async (event) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text || disabled) return;
    try {
      await onSend(text);
      setDraft('');
    } catch (_error) {
      // Keep draft content intact when send fails.
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit(event);
    }
  };

  return (
    <form className={styles.composer} onSubmit={submit}>
      <input
        className={styles.input}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={`Message #${channelName || 'channel'}...`}
        aria-label="Message composer"
        disabled={disabled}
      />
      <button type="submit" className={styles.sendBtn} disabled={!draft.trim() || disabled}>
        Send
      </button>
    </form>
  );
}
