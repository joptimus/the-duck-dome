import { statusColors } from "../../constants/agents";
import { BoltIcon } from "../icons";
import styles from "./StatusTag.module.css";

export function StatusTag({ status }) {
  if (!status) {
    return null;
  }

  const color = statusColors[status] || statusColors.IDLE;
  const isAttacking = status === "ATTACKING";

  return (
    <span
      className={`${styles.tag} ${isAttacking ? styles.attacking : ""}`.trim()}
      style={{
        color,
        background: `${color}12`,
        border: `1px solid ${color}25`,
      }}
    >
      {isAttacking ? <BoltIcon size={12} color={color} glow={false} /> : null}
      {status}
    </span>
  );
}

