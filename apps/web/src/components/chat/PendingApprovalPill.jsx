import { ShieldIcon } from "../icons";
import styles from "./PendingApprovalPill.module.css";

export function PendingApprovalPill({ count }) {
  if (!count) {
    return null;
  }

  return (
    <div className={styles.pill}>
      <ShieldIcon size={15} color="var(--warning)" />
      <span className={styles.label}>{count} PENDING</span>
    </div>
  );
}

