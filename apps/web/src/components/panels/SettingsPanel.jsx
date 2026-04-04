import { useState, useEffect, useCallback } from "react";
import { BoltIcon } from "../icons";
import { SectionLabel } from "../primitives";
import { RightPanel } from "./RightPanel";
import { applyUiSettings, loadUiSettings, saveUiSettings } from "../../features/settings/uiPreferences";
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

function FieldInput({ label, value, onChange }) {
  return (
    <div className={styles.field}>
      <label className={styles.fieldLabel}>{label}</label>
      <input className={styles.fieldInput} value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

function FieldSelect({ label, value, options, onChange }) {
  return (
    <div className={styles.field}>
      <label className={styles.fieldLabel}>{label}</label>
      <select className={styles.fieldSelect} value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((option) => (
          <option key={option}>{option}</option>
        ))}
      </select>
    </div>
  );
}

function Toggle({ label, on, onChange }) {
  return (
    <div className={styles.toggleRow}>
      <span className={styles.toggleLabel}>{label}</span>
      <div
        className={`${styles.toggleTrack} ${on ? styles.toggleOn : ""}`.trim()}
        onClick={() => onChange(!on)}
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
  const [settings, setSettings] = useState(loadUiSettings);
  const [toast, setToast] = useState(false);
  const [showAgentWindows, setShowAgentWindows] = useState(false);

  useEffect(() => {
    if (open) {
      setSettings(loadUiSettings());
      fetchSettings().then((s) => setShowAgentWindows(Boolean(s.show_agent_windows)));
    }
  }, [open]);

  const update = useCallback((key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleShowWindowsToggle = (value) => {
    setShowAgentWindows(value);
    patchSettings({ show_agent_windows: value }).catch(() => {
      setShowAgentWindows(!value);
    });
  };

  const handleApply = () => {
    saveUiSettings(settings);
    applyUiSettings(settings);
    if (settings.desktopNotifications && typeof Notification !== "undefined" && Notification.permission === "default") {
      Notification.requestPermission();
    }
    setToast(true);
    setTimeout(() => setToast(false), 2000);
  };

  const handleCancel = () => {
    setSettings(loadUiSettings());
    onClose();
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
        <FieldInput label="Name" value={settings.name} onChange={(v) => update("name", v)} />
        <div className={styles.fieldRow}>
          <FieldSelect label="Font" value={settings.font} options={["Sans", "Mono"]} onChange={(v) => update("font", v)} />
          <FieldSelect label="Contrast" value={settings.contrast} options={["Normal", "High"]} onChange={(v) => update("contrast", v)} />
        </div>
      </Section>

      <Section title="Behavior">
        <div className={styles.fieldRow}>
          <FieldInput label="Loop guard" value={settings.loopGuard} onChange={(v) => update("loopGuard", v)} />
          <FieldSelect
            label="Rule refresh"
            value={settings.ruleRefresh}
            options={["Every 10 triggers", "Every 5"]}
            onChange={(v) => update("ruleRefresh", v)}
          />
        </div>
      </Section>

      <Section title="Notifications">
        <Toggle label="Desktop notifications" on={settings.desktopNotifications} onChange={(v) => update("desktopNotifications", v)} />
        <Toggle label="Sounds enabled" on={settings.soundsEnabled} onChange={(v) => update("soundsEnabled", v)} />
      </Section>

      <Section title="Sounds">
        <FieldSelect label="Default sound" value={settings.defaultSound} options={["Soft Chime", "Ping", "None"]} onChange={(v) => update("defaultSound", v)} />
      </Section>

      <Section title="Agents">
        <Toggle label="Show agent windows" on={showAgentWindows} onChange={handleShowWindowsToggle} />
      </Section>

      <div className={styles.actions}>
        <button type="button" className={styles.cancelBtn} onClick={handleCancel}>
          Cancel
        </button>
        <button type="button" className={styles.applyBtn} onClick={handleApply}>
          <div className={styles.shimmerOverlay} />
          <span className={styles.applyContent}>
            <BoltIcon size={11} color="#FFFFFF" glow={false} />
            APPLY
          </span>
        </button>
      </div>

      {toast && (
        <div className={styles.toast}>Settings saved</div>
      )}
    </RightPanel>
  );
}
