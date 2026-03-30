import styles from "./ToolbarBtn.module.css";

export function ToolbarBtn({ children, active = false, onClick, title, type = "button" }) {
  return (
    <button
      type={type}
      className={`${styles.btn} ${active ? styles.active : ""}`.trim()}
      onClick={onClick}
      title={title}
    >
      {children}
    </button>
  );
}

