import { useState, useEffect } from "react";
import { BoltIcon } from "../icons";
import { SectionLabel } from "../primitives";
import { RightPanel } from "./RightPanel";
import styles from "./SettingsPanel.module.css";

const API_BASE = (import.meta.env.VITE_API_BASE ?? "http://localhost:8000").replace(/\/$/, "");

async function fetchSettings() {
  try {
    const r = await fetch(`${API_BASE}/api/settings`);
    if (r.ok) return r.json();
  } catch { /* ignore */ }
  return { show_agent_windows: false };
}

async function patchSettings(patch) {
  const r = await fetch(`${API_BASE}/api/settings`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(`PATCH /api/settings failed: ${r.status}`);
  return r.json();
}

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

function Toggle({ label, defaultOn = false, on: controlledOn, onChange }) {
  const [internalOn, setInternalOn] = useState(defaultOn);
  const isControlled = controlledOn !== undefined;
  const on = isControlled ? controlledOn : internalOn;
  const handleClick = () => {
    if (isControlled) {
      onChange?.(!on);
    } else {
      setInternalOn(!internalOn);
    }
  };
  return (
    <div className={styles.toggleRow}>
      <span className={styles.toggleLabel}>{label}</span>
      <div
        className={`${styles.toggleTrack} ${on ? styles.toggleOn : ""}`.trim()}
        onClick={handleClick}
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
  const [showAgentWindows, setShowAgentWindows] = useState(false);

  useEffect(() => {
    if (open) {
      fetchSettings().then((s) => setShowAgentWindows(Boolean(s.show_agent_windows)));
    }
  }, [open]);

  const handleShowWindowsToggle = (value) => {
    setShowAgentWindows(value);
    patchSettings({ show_agent_windows: value }).catch(() => {
      setShowAgentWindows(!value);
    });
  };

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

      <Section title="Agents">
        <Toggle
          label="Show agent windows"
          on={showAgentWindows}
          onChange={handleShowWindowsToggle}
        />
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

