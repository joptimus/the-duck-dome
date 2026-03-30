import styles from "./SectionLabel.module.css";

export function SectionLabel({ children, color = "#00D4FF" }) {
  return (
    <span className={styles.label} style={{ color, textShadow: `0 0 8px ${color}50` }}>
      <span
        className={styles.dot}
        style={{ background: color, boxShadow: `0 0 8px ${color}, 0 0 16px ${color}50` }}
      />
      {children}
    </span>
  );
}

