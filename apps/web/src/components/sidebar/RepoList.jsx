import { SectionLabel } from '../primitives/SectionLabel';
import { FolderIcon, PlusIcon, RefreshIcon, CubeIcon } from '../icons/Icons';
import styles from './RepoList.module.css';

export function RepoList({ repos }) {
  return (
    <div>
      <div className={styles.header}>
        <SectionLabel color="var(--purple)">Repos</SectionLabel>
        <div className={styles.headerIcons}>
          <span className={styles.headerIcon}>
            <FolderIcon size={12} color="var(--text-muted)" />
          </span>
          <span className={styles.headerIcon}>
            <PlusIcon size={12} color="var(--purple)" />
          </span>
          <span className={styles.headerIcon}>
            <RefreshIcon size={12} color="var(--purple)" />
          </span>
        </div>
      </div>
      {repos.map((repo) => (
        <div key={repo} className={styles.row}>
          <CubeIcon size={11} color="var(--text-muted)" />
          <span className={styles.repoName}>{repo}</span>
        </div>
      ))}
    </div>
  );
}
