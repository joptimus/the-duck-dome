import { useState } from 'react';
import { SectionLabel } from '../primitives/SectionLabel';
import { FolderIcon, PlusIcon, XIcon, RefreshIcon, GitHubIcon } from '../icons/Icons';
import AddRepoForm from './AddRepoForm';
import styles from './RepoList.module.css';

function shortenPath(fullPath) {
  const home = fullPath.match(/^(\/Users\/[^/]+|\/home\/[^/]+|[A-Z]:\\Users\\[^\\]+)/);
  if (home) return fullPath.replace(home[0], '~');
  return fullPath;
}

function RepoRow({ name, path, active, onRemove }) {
  return (
    <div className={styles.row}>
      <span className={styles.repoIcon}>
        <GitHubIcon size={14} color={active ? 'var(--purple)' : 'var(--text-muted)'} />
      </span>
      <div className={styles.rowContent}>
        <span className={`${styles.repoName} ${active ? styles.repoNameActive : ''}`}>
          {name}
        </span>
        <span className={styles.repoPath}>{shortenPath(path)}</span>
      </div>
      <button
        className={styles.deleteBtn}
        onClick={(e) => { e.stopPropagation(); onRemove(); }}
        title="Remove repo"
      >
        <XIcon size={12} color="var(--error)" />
      </button>
    </div>
  );
}

export function RepoList({ repos, onAddRepo, onRemoveRepo, onRefreshRepos, onBrowseRepo }) {
  const [showForm, setShowForm] = useState(false);

  const handleBrowseHeader = async () => {
    const picked = await onBrowseRepo();
    if (picked) {
      await onAddRepo(picked);
    }
  };

  const handleAdd = async (path) => {
    await onAddRepo(path);
    setShowForm(false);
  };

  return (
    <div>
      <div className={styles.header}>
        <SectionLabel color="var(--purple)">Repos</SectionLabel>
        <div className={styles.headerIcons}>
          <button className={styles.headerIconMuted} onClick={handleBrowseHeader} title="Browse for folder">
            <FolderIcon size={14} color="var(--text-muted)" />
          </button>
          <button
            className={styles.headerIcon}
            onClick={() => setShowForm(!showForm)}
            title={showForm ? 'Close' : 'Add repo'}
          >
            {showForm
              ? <XIcon size={14} color="var(--purple)" />
              : <PlusIcon size={14} color="var(--purple)" />
            }
          </button>
          <button className={styles.headerIcon} onClick={onRefreshRepos} title="Refresh repos">
            <RefreshIcon size={14} color="var(--purple)" />
          </button>
        </div>
      </div>

      {showForm && (
        <AddRepoForm
          onAdd={handleAdd}
          onCancel={() => setShowForm(false)}
          onBrowse={onBrowseRepo}
        />
      )}

      <div className={styles.list}>
        {repos.map((repo, idx) => (
          <RepoRow
            key={repo.path}
            name={repo.name}
            path={repo.path}
            active={repo.active || false}
            onRemove={() => onRemoveRepo(repo.path)}
          />
        ))}
      </div>
    </div>
  );
}
