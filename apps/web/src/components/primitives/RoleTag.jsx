import styles from "./RoleTag.module.css";

export function RoleTag({ name }) {
  return <span className={styles.tag}>{name}</span>;
}

