import { useState, useMemo } from "react";
import { agentMeta, allAgentTypes } from "../../constants/agents";

function formatUptime(startedAt) {
  if (!startedAt) return "";
  const seconds = Math.floor(Date.now() / 1000 - startedAt);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remMin = minutes % 60;
  return `${hours}h ${remMin}m`;
}
import { ElectricPulse } from "../effects/ElectricPulse";
import {
  AgentLogo,
  EditIcon,
  PlayIcon,
  PlusIcon,
  PowerIcon,
  StopIcon,
  TerminalIcon,
  TrashIcon,
  UsersIcon,
} from "../icons";
import { Dot } from "../primitives/Dot";
import styles from "./AgentsPanel.module.css";

export function AgentsPanel({
  open,
  onClose,
  channelName = "general",
  agents = [],
  repos = [],
  onToggleAgent,
  onRemoveAgent,
  onAddAgent,
}) {
  const [editingPrompt, setEditingPrompt] = useState(null);
  const [draftPrompts, setDraftPrompts] = useState({});
  const [adding, setAdding] = useState(false);
  const [newAgent, setNewAgent] = useState({ type: "", prompt: "" });

  if (!open) {
    return null;
  }

  const runCount = agents.filter((agent) => agent.running).length;
  const availableTypes = allAgentTypes.filter((type) => !agents.find((agent) => agent.agent === type));

  function handleAdd() {
    if (!newAgent.type) {
      return;
    }
    onAddAgent?.({ ...newAgent, workspace: channelName });
    setNewAgent({ type: "", prompt: "" });
    setAdding(false);
  }

  return (
    <div className={styles.panel}>
      <div className={styles.accentBar} />
      <ElectricPulse vertical color="#A855F7" minDelay={4000} maxDelay={10000} />

      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <UsersIcon size={14} color="var(--blue)" />
          <span className={styles.headerTitle}>AGENTS</span>
          <span
            className={styles.runCount}
            style={{ color: runCount > 0 ? "var(--success)" : "var(--text-muted)" }}
          >
            {runCount} running
          </span>
        </div>
        <button type="button" className={styles.closeBtn} onClick={onClose}>
          &times;
        </button>
      </div>

      <div className={styles.channelBar}>
        <div className={styles.channelLabel}>Channel</div>
        <div className={styles.channelName}>#{channelName}</div>
      </div>

      <div className={styles.agentList}>
        {agents.map((agent, index) => {
          const meta = agentMeta[agent.agent];
          if (!meta) {
            return null;
          }

          if (index === 0) console.log("[AgentsPanel] agent data:", JSON.stringify(agent));
          const isEditing = editingPrompt === index;
          return (
            <div key={agent.id || agent.agent} className={styles.agentCard} style={{ opacity: agent.running ? 1 : 0.6 }}>
              <div className={styles.agentHeaderRow}>
                <div
                  className={styles.avatar}
                  style={{
                    background: `${meta.color}15`,
                    borderColor: agent.running ? `${meta.color}50` : "var(--border)",
                  }}
                >
                  <AgentLogo agent={agent.agent} size={18} />
                </div>
                <div className={styles.agentInfo}>
                  <div className={styles.agentNameRow}>
                    <span className={styles.agentLabel} style={{ color: meta.color }}>
                      {meta.label}
                    </span>
                    <Dot color={agent.running ? "var(--success)" : "var(--text-muted)"} size={6} />
                    <span className={styles.statusText}>{agent.running ? "running" : "stopped"}</span>
                  </div>
                  {agent.running ? (
                    <div className={styles.pidLine}>
                      PID {agent.pid || "—"} &middot; up {formatUptime(agent.started_at)}
                    </div>
                  ) : null}
                </div>
                <button
                  type="button"
                  className={`${styles.toggleBtn} ${agent.running ? styles.stopBtn : styles.startBtn}`}
                  onClick={() => onToggleAgent?.(agent)}
                >
                  {agent.running ? (
                    <StopIcon size={12} color="var(--error)" />
                  ) : (
                    <PlayIcon size={10} color="var(--success)" />
                  )}
                </button>
              </div>

              <div className={styles.fieldGroup}>
                <div className={styles.fieldLabelRow}>
                  <span className={styles.fieldLabel}>
                    <TerminalIcon size={10} color="var(--text-muted)" />
                    System prompt
                  </span>
                  <button
                    type="button"
                    className={styles.editBtn}
                    style={{ color: isEditing ? meta.color : "var(--text-muted)" }}
                    onClick={() => setEditingPrompt(isEditing ? null : index)}
                  >
                    <EditIcon size={11} color="currentColor" />
                  </button>
                </div>

                {isEditing ? (
                  <textarea
                    className={styles.promptTextarea}
                    value={draftPrompts[index] ?? agent.prompt}
                    rows={4}
                    style={{ borderColor: `${meta.color}40` }}
                    onChange={(event) =>
                      setDraftPrompts((prev) => ({ ...prev, [index]: event.target.value }))
                    }
                  />
                ) : (
                  <div
                    className={styles.promptCollapsed}
                    role="button"
                    tabIndex={0}
                    onClick={() => setEditingPrompt(index)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setEditingPrompt(index);
                      }
                    }}
                  >
                    {draftPrompts[index] ?? agent.prompt}
                    <div className={styles.promptFade} />
                  </div>
                )}
              </div>

              {!agent.running ? (
                <div className={styles.removeRow}>
                  <button type="button" className={styles.removeBtn} onClick={() => onRemoveAgent?.(agent)}>
                    <TrashIcon size={10} color="currentColor" />
                    Remove from channel
                  </button>
                </div>
              ) : null}
            </div>
          );
        })}

        {!adding ? (
          <div className={styles.addSection}>
            <button
              type="button"
              className={styles.addTrigger}
              disabled={availableTypes.length === 0}
              onClick={() => setAdding(true)}
            >
              <PlusIcon size={12} color="currentColor" />
              {availableTypes.length ? `Add agent to #${channelName}` : "All agents assigned"}
            </button>
          </div>
        ) : (
          <div className={styles.addForm}>
            <div className={styles.addFormTitle}>Add Agent</div>

            <div className={styles.fieldLabel}>Agent</div>
            <div className={styles.typePicker}>
              {availableTypes.map((type) => {
                const meta = agentMeta[type];
                const selected = newAgent.type === type;
                return (
                  <button
                    key={type}
                    type="button"
                    className={styles.typeBtn}
                    style={{
                      color: selected ? meta.color : undefined,
                      background: selected ? `${meta.color}15` : undefined,
                      borderColor: selected ? `${meta.color}50` : undefined,
                    }}
                    onClick={() => setNewAgent((prev) => ({ ...prev, type }))}
                  >
                    <AgentLogo agent={type} size={14} />
                    {meta.label}
                  </button>
                );
              })}
            </div>

            <div className={styles.fieldLabel}>
              <TerminalIcon size={10} color="var(--text-muted)" />
              System prompt
            </div>
            <textarea
              className={styles.promptTextarea}
              value={newAgent.prompt}
              onChange={(event) => setNewAgent((prev) => ({ ...prev, prompt: event.target.value }))}
              rows={3}
              placeholder="Define how this agent should behave..."
            />

            <div className={styles.addActions}>
              <button
                type="button"
                className={styles.cancelBtn}
                onClick={() => {
                  setAdding(false);
                  setNewAgent({ type: "", prompt: "" });
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className={styles.spawnBtn}
                disabled={!newAgent.type}
                onClick={handleAdd}
              >
                {newAgent.type ? <div className={styles.shimmerOverlay} /> : null}
                <span className={styles.spawnContent}>
                  <PowerIcon size={11} color="currentColor" />
                  SPAWN
                </span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

