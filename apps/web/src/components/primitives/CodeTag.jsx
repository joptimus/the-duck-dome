import styles from "./CodeTag.module.css";

export function CodeTag({ children }) {
  return <code className={styles.tag}>{children}</code>;
}

