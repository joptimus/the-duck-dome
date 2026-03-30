import { useEffect } from 'react';
import styles from './Modal.module.css';

export function Modal({
  open,
  onClose,
  title,
  children,
  showTopBar = true,
  showHeader = true,
  cardClassName = '',
  bodyClassName = '',
}) {
  useEffect(() => {
    if (!open) return;
    const handleKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={[styles.card, cardClassName].filter(Boolean).join(' ')} onClick={(e) => e.stopPropagation()}>
        {showTopBar && <div className={styles.topBar} />}
        {showHeader && (
          <div className={styles.header}>
            <div className={styles.title}>{title}</div>
            <button className={styles.closeBtn} onClick={onClose}>
              &times;
            </button>
          </div>
        )}
        <div className={[styles.body, bodyClassName].filter(Boolean).join(' ')}>{children}</div>
      </div>
    </div>
  );
}
