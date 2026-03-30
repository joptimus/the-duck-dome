import { useState } from 'react';
import { FolderIcon, GitBranchIcon, CheckIcon } from '../icons/Icons';
import styles from './AddRepoForm.module.css';

function deriveRepoName(path) {
  if (!path) return '';
  const segments = path.replace(/\\/g, '/').replace(/\/+$/, '').split('/');
  return segments[segments.length - 1] || '';
}

export default function AddRepoForm({ onAdd, onCancel, onBrowse }) {
  const [pathValue, setPathValue] = useState('');
  const repoName = deriveRepoName(pathValue);
  const hasPath = pathValue.trim().length > 0;

  const handleBrowse = async () => {
    const result = await onBrowse();
    if (result) setPathValue(result);
  };

  const handleSubmit = () => {
    if (!hasPath) return;
    onAdd(pathValue.trim());
    setPathValue('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && hasPath) handleSubmit();
    if (e.key === 'Escape') onCancel();
  };

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <label className={styles.label} htmlFor="repo-path-input">
          <FolderIcon size={10} color="var(--text-muted)" />
          <span>Path to repository</span>
        </label>

        <div className={styles.inputWrap}>
          <input
            id="repo-path-input"
            className={`${styles.input} ${hasPath ? styles.inputFilled : ''}`}
            type="text"
            placeholder="/Users/james/DevApps/..."
            value={pathValue}
            onChange={(e) => setPathValue(e.target.value)}
            onKeyDown={handleKeyDown}
            autoFocus
          />
          <button className={styles.browseBtn} onClick={handleBrowse} title="Browse" aria-label="Browse for folder">
            <FolderIcon size={15} color="var(--purple)" />
          </button>
        </div>

        {hasPath && (
          <div className={styles.preview}>
            <GitBranchIcon size={13} color="var(--success)" />
            <div className={styles.previewText}>
              <span className={styles.previewName}>{repoName}</span>
              <span className={styles.previewPath}>{pathValue}</span>
            </div>
            <CheckIcon size={12} color="var(--success)" />
          </div>
        )}

        <div className={styles.actions}>
          <button className={styles.cancelBtn} onClick={onCancel}>Cancel</button>
          <button
            className={`${styles.addBtn} ${hasPath ? styles.addBtnActive : ''}`}
            onClick={handleSubmit}
            disabled={!hasPath}
          >
            ADD REPO
          </button>
        </div>
      </div>
    </div>
  );
}
