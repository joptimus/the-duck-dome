import { RulesIcon } from "../icons";
import { RightPanel } from "./RightPanel";
import styles from "./RulesPanel.module.css";

export function RulesPanel({ open, onClose, ruleCount = 0, maxRules = 10 }) {
  return (
    <RightPanel
      open={open}
      onClose={onClose}
      title={`RULES ${ruleCount}/${maxRules}`}
      width={380}
      icon={<RulesIcon size={14} color="var(--blue)" />}
    >
      <div className={styles.topRow}>
        <button type="button" className={styles.remindBtn}>
          Remind agents
        </button>
      </div>

      <div className={styles.emptyCard}>
        <div className={styles.emptyTitle}>+ No rules yet</div>
        <div className={styles.emptyDesc}>Tell your agents how to work</div>
      </div>

      <div className={styles.footnote}>New rules are sent on the next agent trigger</div>
    </RightPanel>
  );
}

