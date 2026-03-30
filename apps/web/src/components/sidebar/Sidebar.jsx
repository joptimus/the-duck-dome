import { useState } from 'react';
import { BoltIcon } from '../icons/BoltIcon';
import { SectionLabel } from '../primitives/SectionLabel';
import { ChannelList } from './ChannelList';
import { RepoList } from './RepoList';
import { SidebarFooter } from './SidebarFooter';
import styles from './Sidebar.module.css';

export function Sidebar({
  channels,
  repos,
  activeChannel,
  onSelectChannel,
  onCreateChannel,
  onDeleteChannel,
  onSessionLaunch,
  userName = "James",
  userInitial = "J",
  onAddRepo,
  onRemoveRepo,
  onRefreshRepos,
  onBrowseRepo,
  onOpenRepoChannel,
}) {
  const [pinnedOpen, setPinnedOpen] = useState(false);

  return (
    <div className={styles.sidebar}>
      {/* Zone 1: Logo Header */}
      <div className={styles.logoHeader}>
        <div className={styles.gradientLine} />
        <div className={styles.logoIcon}>
          <BoltIcon size={18} color="var(--blue)" />
        </div>
        <div className={styles.logoText}>
          <div className={styles.logoTitle}>THE DUCKDOME</div>
          <div className={styles.logoSubtitle}>AI AGENT BATTLEGROUND</div>
        </div>
      </div>

      {/* Zone 2: Pinned Drawer */}
      <div className={styles.pinnedSection}>
        <div
          className={styles.pinnedHeader}
          onClick={() => setPinnedOpen(!pinnedOpen)}
        >
          <span
            className={styles.pinnedChevron}
            style={{ transform: pinnedOpen ? 'rotate(90deg)' : 'none' }}
          >
            &#9654;
          </span>
          <span className={styles.pinnedLabel}>Pinned</span>
        </div>
        {pinnedOpen && (
          <div className={styles.pinnedEmpty}>No pinned messages</div>
        )}
      </div>

      {/* Zone 3 + 4: Channels + Repos (scrollable) */}
      <div className={styles.scrollArea}>
        {/* Channels */}
        <div className={styles.sectionHeader}>
          <SectionLabel>Channels</SectionLabel>
          <button className={styles.addBtn} onClick={onCreateChannel}>+</button>
        </div>
        <ChannelList
          channels={channels}
          activeChannel={activeChannel}
          onSelect={onSelectChannel}
          onDelete={onDeleteChannel}
        />

        {/* Separator */}
        <div className={styles.separator} />

        {/* Repos */}
        <RepoList
          repos={repos}
          onAddRepo={onAddRepo}
          onRemoveRepo={onRemoveRepo}
          onRefreshRepos={onRefreshRepos}
          onBrowseRepo={onBrowseRepo}
          onOpenRepo={onOpenRepoChannel}
        />
      </div>

      {/* Zone 5: User Footer */}
      <SidebarFooter
        userName={userName}
        userInitial={userInitial}
        onSessionLaunch={onSessionLaunch}
      />
    </div>
  );
}
