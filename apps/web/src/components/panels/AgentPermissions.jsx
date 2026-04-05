import { useEffect, useMemo, useState } from "react";
import { agentStore } from "../../stores/agentStore";
import * as Icons from "../icons";
import styles from "./AgentPermissions.module.css";

const iconMap = {
  ...Icons,
};

const autoApproveOptions = [
  {
    value: "none",
    label: "Ask every time",
    description: "All tool use requires manual approval",
  },
  {
    value: "tool",
    label: "Approved tools only",
    description: "Auto-run enabled tools, ask for others",
  },
  {
    value: "all",
    label: "Full autonomy",
    description: "Never ask - run everything without approval",
    caution: true,
  },
];

function getToolIcon(iconName) {
  return iconMap[iconName] || Icons.BoltIcon || Icons.GearIcon;
}

function getRiskTagTone(toolKey) {
  if (toolKey === "bash") return "success";
  if (toolKey === "write_file") return "warning";
  return "warning";
}

function getSummaryTagLabel(tool) {
  const firstKeyToken = String(tool.key || "")
    .split(/[_-]/)
    .filter(Boolean)[0];

  if (firstKeyToken) {
    return firstKeyToken;
  }

  return String(tool.label || "tool")
    .toLowerCase()
    .split(/[ /]/)
    .filter(Boolean)[0] || "tool";
}

export function AgentPermissions({
  agent,
  permissions,
  agentColor,
  expanded,
  onToggleExpand,
}) {
  const [loopDraft, setLoopDraft] = useState(String(permissions.maxLoops));

  useEffect(() => {
    setLoopDraft(String(permissions.maxLoops));
  }, [permissions.maxLoops]);

  const summaryTools = useMemo(
    () => permissions.tools.filter((tool) => tool.enabled && tool.highRisk),
    [permissions.tools],
  );

  const handleLoopCommit = (value) => {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isFinite(parsed)) {
      setLoopDraft(String(permissions.maxLoops));
      return;
    }
    const nextValue = Math.min(100, Math.max(1, parsed));
    setLoopDraft(String(nextValue));
    void agentStore.setMaxLoops(agent, nextValue);
  };

  return (
    <div className={styles.root} style={{ "--agent-color": agentColor }}>
      <button
        type="button"
        className={styles.toggleRow}
        aria-expanded={expanded}
        onClick={onToggleExpand}
      >
        <span className={styles.toggleLead}>
          <span className={styles.chevron} aria-hidden="true">
            <Icons.ChevronIcon size={9} color="currentColor" rotation={expanded ? 90 : 0} />
          </span>
          <Icons.ShieldIcon size={11} color="currentColor" />
          <span className={styles.toggleLabel}>Permissions</span>
        </span>

        {!expanded ? (
          <span className={styles.summaryTags}>
            {summaryTools.map((tool) => (
              <span
                key={tool.key}
                className={`${styles.summaryTag} ${styles[`summaryTag${getRiskTagTone(tool.key)[0].toUpperCase()}${getRiskTagTone(tool.key).slice(1)}`]}`}
              >
                {getSummaryTagLabel(tool)}
              </span>
            ))}
            {permissions.autoApprove !== "none" ? (
              <span className={`${styles.summaryTag} ${styles.summaryTagInfo}`}>auto</span>
            ) : null}
          </span>
        ) : null}
      </button>

      {expanded ? (
        <div className={styles.panel}>
          <section>
            <div className={styles.sectionTitle}>Tool Access</div>
            <div className={styles.toolList}>
              {permissions.tools.map((tool) => {
                const ToolIcon = getToolIcon(tool.icon);
                return (
                  <div key={tool.key} className={styles.toolRow}>
                    <ToolIcon
                      size={12}
                      color={tool.enabled ? "var(--agent-color)" : "var(--text-muted)"}
                    />
                    <div className={styles.toolText}>
                      <div className={tool.enabled ? styles.toolLabelEnabled : styles.toolLabelDisabled}>
                        {tool.label}
                      </div>
                      <div className={styles.toolDescription}>{tool.description}</div>
                    </div>
                    <button
                      type="button"
                      className={`${styles.toolToggle} ${tool.enabled ? styles.toolToggleOn : styles.toolToggleOff}`}
                      aria-pressed={tool.enabled}
                      aria-label={`${tool.enabled ? "Disable" : "Enable"} ${tool.label}`}
                      onClick={() => void agentStore.toggleTool(agent, tool.key)}
                    >
                      <span className={`${styles.toolToggleThumb} ${tool.enabled ? styles.toolToggleThumbOn : ""}`} />
                    </button>
                  </div>
                );
              })}
            </div>
          </section>

          <section className={styles.sectionSpacing}>
            <div className={styles.sectionTitle}>Auto-Approve</div>
            <div className={styles.radioStack}>
              {autoApproveOptions.map((option) => {
                const selected = permissions.autoApprove === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    className={`${styles.radioOption} ${selected ? styles.radioOptionSelected : ""}`}
                    onClick={() => void agentStore.setAutoApprove(agent, option.value)}
                  >
                    <span className={`${styles.radioDot} ${selected ? styles.radioDotSelected : ""}`}>
                      {selected ? <span className={styles.radioDotInner} /> : null}
                    </span>
                    <span className={styles.radioContent}>
                      <span className={styles.radioHeader}>
                        <span className={selected ? styles.radioLabelSelected : styles.radioLabel}>
                          {option.label}
                        </span>
                        {option.caution ? (
                          <span className={styles.cautionBadge}>caution</span>
                        ) : null}
                      </span>
                      <span className={styles.radioDescription}>{option.description}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          <section className={styles.sectionSpacing}>
            <div className={styles.sectionTitle}>Loop Guard</div>
            <div className={styles.loopRow}>
              <label className={styles.loopLabel} htmlFor={`${agent}-max-loops`}>
                Max iterations before pause
              </label>
              <input
                id={`${agent}-max-loops`}
                className={styles.loopInput}
                type="number"
                min="1"
                max="100"
                value={loopDraft}
                onChange={(event) => {
                  setLoopDraft(event.target.value);
                  const parsed = Number.parseInt(event.target.value, 10);
                  if (Number.isFinite(parsed)) {
                    void agentStore.setMaxLoops(agent, parsed);
                  }
                }}
                onBlur={(event) => handleLoopCommit(event.target.value)}
              />
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}
