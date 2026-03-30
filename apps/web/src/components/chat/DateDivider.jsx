import styles from './DateDivider.module.css';

export function DateDivider({ label }) {
  return (
    <div className={styles.divider}>
      <div className={styles.lineLeft} />
      <span className={styles.label}>{label}</span>
      <div className={styles.lineRight} />
    </div>
  );
}
