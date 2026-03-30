import { useState } from "react";
import { agentMeta } from "../../constants/agents";
import { ElectricPulse } from "../effects/ElectricPulse";
import { AgentLogo, BoltIcon, ChevronIcon, PauseIcon, ShuffleIcon, TerminalIcon } from "../icons";
import { Dot, StatusTag } from "../primitives";
import styles from "./ActivityPanel.module.css";

const OUTPUT_COLORS = {
  info: "var(--text-secondary)",
  cmd: "var(--blue)",
  ok: "var(--success)",
  warn: "var(--warning)",
  err: "var(--error)",
};

export function ActivityPanel({ open, onClose, agentActivity = {} }) {
  const [expanded, setExpanded] = useState({});
  const [fullLog, setFullLog] = useState(null);

  if (!open) {
    return null;
  }

  const activeCount = Object.keys(agentActivity).length;

  function toggle(agent) {
    setFullLog(null);
    setExpanded((prev) => ({ ...prev, [agent]: !prev[agent] }));
  }

  if (fullLog) {
    const data = agentActivity[fullLog];
    const meta = agentMeta[fullLog];
    if (!data || !meta) {
      return null;
    }

    return (
      <div className={styles.panel}>
        <div className={styles.accentBar} style={{ background: meta.color, opacity: 0.6 }} />

        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <button type="button" className={styles.backBtn} onClick={() => setFullLog(null)}>
              <ChevronIcon size={12} color="var(--text-secondary)" rotation={180} />
            </button>
            <AgentLogo agent={fullLog} size={16} />
            <span className={styles.headerTitle} style={{ color: meta.color }}>
              {meta.label} LOG
            </span>
          </div>
          <button type="button" className={styles.closeBtn} onClick={onClose}>
            &times;
          </button>
        </div>

        <div className={styles.taskInfoBar} style={{ background: `${meta.color}04` }}>
          <div className={styles.taskInfoRow}>
            <span className={styles.taskName}>{data.task}</span>
            <div className={styles.taskMeta}>
              <StatusTag status={data.status} />
              <span className={styles.elapsed}>{data.elapsed}</span>
            </div>
          </div>
          <div className={styles.taskFile}>{data.file}</div>
        </div>

        <div className={styles.fullTerminal}>
          {data.output.map((line, index) => (
            <div key={index} className={styles.termLine}>
              <span className={styles.termTimestamp}>{line.t}</span>
              <span
                style={{
                  color: OUTPUT_COLORS[line.type] || "var(--text-secondary)",
                  wordBreak: "break-all",
                }}
              >
                {line.text}
              </span>
            </div>
          ))}
        </div>

        <div className={styles.bottomBar}>
          <button type="button" className={styles.actionBtn}>
            <PauseIcon size={11} color="currentColor" />
            Pause
          </button>
          <button type="button" className={styles.actionBtn}>
            <ShuffleIcon size={11} color="currentColor" />
            Reassign
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      <div className={styles.accentBar} />
      <ElectricPulse vertical color="#A855F7" minDelay={4000} maxDelay={10000} />

      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <BoltIcon size={14} color="var(--blue)" glow={false} />
          <span className={styles.headerTitle}>ACTIVITY</span>
          <span className={styles.activeCount}>{activeCount} active</span>
        </div>
        <button type="button" className={styles.closeBtn} onClick={onClose}>
          &times;
        </button>
      </div>

      <div className={styles.agentList}>
        {Object.entries(agentActivity).map(([agent, data]) => {
          const meta = agentMeta[agent];
          if (!meta) {
            return null;
          }

          const isOpen = expanded[agent];
          const latestLine = data.output[0];
          return (
            <div key={agent} className={styles.agentRow}>
              <div
                className={styles.agentHeader}
                onClick={() => toggle(agent)}
                style={{ background: isOpen ? `${meta.color}06` : undefined }}
              >
                <ChevronIcon size={10} color={meta.color} rotation={isOpen ? 90 : 0} />
                <Dot color={meta.color} size={7} />
                <span className={styles.agentLabel} style={{ color: meta.color }}>
                  {meta.label}
                </span>
                <StatusTag status={data.status} />
                <span className={styles.elapsed}>{data.elapsed}</span>
              </div>

              {!isOpen && latestLine ? (
                <div className={styles.preview} onClick={() => toggle(agent)}>
                  <div
                    className={styles.previewText}
                    style={{ color: OUTPUT_COLORS[latestLine.type] || "var(--text-muted)" }}
                  >
                    {latestLine.text}
                  </div>
                </div>
              ) : null}

              {isOpen ? (
                <div className={styles.expandedContent}>
                  <div className={styles.taskCard}>
                    <div className={styles.taskCardName}>{data.task}</div>
                    <div className={styles.taskCardFile}>{data.file}</div>
                  </div>

                  <div className={styles.terminal}>
                    {data.output.map((line, index) => (
                      <div key={index} className={styles.termLine}>
                        <span className={styles.termTimestamp}>{line.t}</span>
                        <span
                          style={{
                            color: OUTPUT_COLORS[line.type] || "var(--text-secondary)",
                            wordBreak: "break-all",
                          }}
                        >
                          {line.text}
                        </span>
                      </div>
                    ))}
                  </div>

                  <div className={styles.quickActions}>
                    <button type="button" className={styles.actionBtn}>
                      <PauseIcon size={11} color="currentColor" />
                      Pause
                    </button>
                    <button type="button" className={styles.actionBtn}>
                      <ShuffleIcon size={11} color="currentColor" />
                      Reassign
                    </button>
                    <button type="button" className={styles.actionBtn} onClick={() => setFullLog(agent)}>
                      <TerminalIcon size={11} color="currentColor" />
                      Full log
                    </button>
                  </div>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

