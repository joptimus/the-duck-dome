import { JobsIcon } from "../icons";
import { RightPanel } from "./RightPanel";
import styles from "./JobsPanel.module.css";

const STATUS_GROUPS = [
  { label: "TO DO", color: "var(--text-muted)" },
  { label: "ACTIVE", color: "var(--success)" },
  { label: "CLOSED", color: "var(--error)" },
];

export function JobsPanel({ open, onClose }) {
  return (
    <RightPanel open={open} onClose={onClose} title="JOBS" width={380} icon={<JobsIcon size={14} color="var(--blue)" />}>
      <div className={styles.emptyCard}>
        <div className={styles.emptyTitle}>+ Create your first job</div>
        <div className={styles.emptyDesc}>
          Track work items with threaded conversations. Use @mentions to loop in agents.
        </div>
      </div>

      {STATUS_GROUPS.map((group) => (
        <div key={group.label} className={styles.statusGroup}>
          <div className={styles.statusHeader} style={{ color: group.color }}>
            <span className={styles.statusChevron}>&#9654;</span>
            {group.label}
          </div>
        </div>
      ))}
    </RightPanel>
  );
}

