import { ElectricPulse } from "../effects/ElectricPulse";
import styles from "./RightPanel.module.css";

export function RightPanel({ open, onClose, title, icon, width = 380, children }) {
  if (!open) {
    return null;
  }

  return (
    <div className={styles.panel} style={{ width }}>
      <div className={styles.accentBar} />
      <ElectricPulse vertical color="#A855F7" minDelay={4000} maxDelay={10000} />
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          {icon}
          <span className={styles.headerTitle}>{title}</span>
        </div>
        <button type="button" className={styles.closeBtn} onClick={onClose}>
          &times;
        </button>
      </div>
      <div className={styles.body}>{children}</div>
    </div>
  );
}

