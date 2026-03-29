import styles from './AmbientOrbs.module.css';

export function AmbientOrbs() {
  return (
    <>
      <div className={`${styles.orb} ${styles.blue}`} />
      <div className={`${styles.orb} ${styles.purple}`} />
    </>
  );
}
