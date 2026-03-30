import { agentMeta } from "../../constants/agents";
import { ElectricPulse } from "../effects/ElectricPulse";
import { AgentLogo, BoltIcon, GearIcon, HelpIcon, JobsIcon, RulesIcon, UsersIcon } from "../icons";
import { PendingApprovalPill } from "../chat/PendingApprovalPill";
import { ToolbarBtn, Waveform } from "../primitives";
import styles from "./TopBar.module.css";

export function TopBar({
  channelName,
  channelAgents = [],
  pendingCount = 0,
  activePanel,
  onTogglePanel,
}) {
  return (
    <div className={styles.bar}>
      <ElectricPulse vertical={false} color="#A855F7" minDelay={5000} maxDelay={12000} />

      <BoltIcon size={14} color="var(--blue)" />
      <span className={styles.channelName}>{channelName}</span>
      <div className={styles.waveformWrap}>
        <Waveform color="var(--blue)" bars={12} />
      </div>

      <div className={styles.spacer} />

      <div
        className={styles.agentStrip}
        style={{
          borderColor: activePanel === "activity" ? "rgba(0, 212, 255, 0.25)" : undefined,
        }}
        onClick={() => onTogglePanel?.("activity")}
      >
        {channelAgents.map((agentConfig) => {
          const meta = agentMeta[agentConfig.agent];
          if (!meta) {
            return null;
          }

          return (
            <div key={agentConfig.agent} className={styles.agentChip}>
              <div className={styles.agentLogoWrap}>
                <AgentLogo agent={agentConfig.agent} size={14} />
                <div
                  className={styles.statusDot}
                  style={{
                    background: agentConfig.running ? "var(--success)" : "var(--text-muted)",
                    boxShadow: agentConfig.running ? "0 0 4px var(--success)" : "none",
                  }}
                />
              </div>
              <span
                className={styles.agentName}
                style={{
                  color: agentConfig.running ? "var(--text-secondary)" : "var(--text-muted)",
                }}
              >
                {meta.label}
              </span>
            </div>
          );
        })}
      </div>

      <PendingApprovalPill count={pendingCount} />

      <div className={styles.toolbar}>
        <ToolbarBtn
          title="Activity"
          active={activePanel === "activity"}
          onClick={() => onTogglePanel?.("activity")}
        >
          <BoltIcon size={14} color="currentColor" glow={false} />
        </ToolbarBtn>
        <ToolbarBtn
          title="Agents"
          active={activePanel === "agents"}
          onClick={() => onTogglePanel?.("agents")}
        >
          <UsersIcon size={14} color="currentColor" />
        </ToolbarBtn>
        <ToolbarBtn
          title="Jobs"
          active={activePanel === "jobs"}
          onClick={() => onTogglePanel?.("jobs")}
        >
          <JobsIcon size={14} color="currentColor" />
        </ToolbarBtn>
        <ToolbarBtn
          title="Rules"
          active={activePanel === "rules"}
          onClick={() => onTogglePanel?.("rules")}
        >
          <RulesIcon size={14} color="currentColor" />
        </ToolbarBtn>
        <ToolbarBtn
          title="Settings"
          active={activePanel === "settings"}
          onClick={() => onTogglePanel?.("settings")}
        >
          <GearIcon size={14} color="currentColor" />
        </ToolbarBtn>
        <ToolbarBtn title="Help">
          <HelpIcon size={14} color="currentColor" />
        </ToolbarBtn>
      </div>
    </div>
  );
}

