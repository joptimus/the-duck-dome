import { useState } from "react";
import { BoltIcon } from "../icons";
import { SectionLabel } from "../primitives";
import { RightPanel } from "./RightPanel";
import styles from "./SettingsPanel.module.css";

function FieldInput({ label, defaultValue }) {
  return (
    <div className={styles.field}>
      <label className={styles.fieldLabel}>{label}</label>
      <input className={styles.fieldInput} defaultValue={defaultValue} />
    </div>
  );
}

function FieldSelect({ label, defaultValue, options }) {
  return (
    <div className={styles.field}>
      <label className={styles.fieldLabel}>{label}</label>
      <select className={styles.fieldSelect} defaultValue={defaultValue}>
        {options.map((option) => (
          <option key={option}>{option}</option>
        ))}
      </select>
    </div>
  );
}

function Toggle({ label, defaultOn = false }) {
  const [on, setOn] = useState(defaultOn);
  return (
    <div className={styles.toggleRow}>
      <span className={styles.toggleLabel}>{label}</span>
      <div
        className={`${styles.toggleTrack} ${on ? styles.toggleOn : ""}`.trim()}
        onClick={() => setOn(!on)}
      >
        <div className={`${styles.toggleCircle} ${on ? styles.toggleCircleOn : ""}`.trim()} />
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className={styles.section}>
      <SectionLabel color="var(--blue)">{title}</SectionLabel>
      <div className={styles.sectionBody}>{children}</div>
    </div>
  );
}

export function SettingsPanel({ open, onClose }) {
  return (
    <RightPanel
      open={open}
      onClose={onClose}
      title="SETTINGS"
      width={380}
      icon={<BoltIcon size={14} color="var(--blue)" />}
    >
      <Section title="Profile">
        <FieldInput label="Name" defaultValue="James" />
        <div className={styles.fieldRow}>
          <FieldSelect label="Font" defaultValue="Sans" options={["Sans", "Mono"]} />
          <FieldSelect label="Contrast" defaultValue="Normal" options={["Normal", "High"]} />
        </div>
      </Section>

      <Section title="Behavior">
        <div className={styles.fieldRow}>
          <FieldInput label="Loop guard" defaultValue="4" />
          <FieldSelect
            label="Rule refresh"
            defaultValue="Every 10 triggers"
            options={["Every 10 triggers", "Every 5"]}
          />
        </div>
      </Section>

      <Section title="Notifications">
        <Toggle label="Desktop notifications" />
        <Toggle label="Sounds enabled" defaultOn />
      </Section>

      <Section title="Sounds">
        <FieldSelect label="Default sound" defaultValue="Soft Chime" options={["Soft Chime", "Ping", "None"]} />
      </Section>

      <div className={styles.actions}>
        <button type="button" className={styles.cancelBtn} onClick={onClose}>
          Cancel
        </button>
        <button type="button" className={styles.applyBtn}>
          <div className={styles.shimmerOverlay} />
          <span className={styles.applyContent}>
            <BoltIcon size={11} color="#FFFFFF" glow={false} />
            APPLY
          </span>
        </button>
      </div>
    </RightPanel>
  );
}

