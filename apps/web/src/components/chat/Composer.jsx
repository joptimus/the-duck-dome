import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { agentMeta } from "../../constants/agents";
import { slashCommands } from "../../constants/composer";
import { AgentLogo, BoltIcon, ClockIcon, MicIcon, UsersIcon } from "../icons";
import { ToolbarBtn } from "../primitives";
import styles from "./Composer.module.css";

function mentionFilterFromInput(value) {
  const match = value.match(/@([a-zA-Z]*)$/);
  return match ? match[1].toLowerCase() : null;
}

export function Composer({
  onSchedule,
  onSendMessage,
  initialValue = "",
  replyMessage = null,
  onCancelReply,
}) {
  const [value, setValue] = useState(initialValue);
  const [showSlash, setShowSlash] = useState(initialValue.startsWith("/"));
  const [showMention, setShowMention] = useState(false);
  const [slashFilter, setSlashFilter] = useState(
    initialValue.startsWith("/") ? initialValue.slice(1).toLowerCase() : "",
  );
  const [mentionFilter, setMentionFilter] = useState("");
  const [selectedIdx, setSelectedIdx] = useState(0);
  const inputRef = useRef(null);

  function resizeInput() {
    const input = inputRef.current;
    if (!input) return;
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 168)}px`;
  }

  useLayoutEffect(() => {
    resizeInput();
  }, [value]);

  const allMentionAgents = useMemo(
    () => Object.entries(agentMeta).filter(([key]) => key !== "user"),
    [],
  );

  const filteredCommands = useMemo(
    () => slashCommands.filter((command) => command.cmd.toLowerCase().includes(slashFilter)),
    [slashFilter],
  );

  const filteredMentions = useMemo(
    () =>
      allMentionAgents.filter(
        ([key, meta]) =>
          key.includes(mentionFilter) || meta.label.toLowerCase().includes(mentionFilter),
      ),
    [allMentionAgents, mentionFilter],
  );

  function closePopups() {
    setShowSlash(false);
    setShowMention(false);
  }

  function focusInput() {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }

  function handleChange(event) {
    const nextValue = event.target.value;
    setValue(nextValue);

    if (nextValue.startsWith("/")) {
      setShowSlash(true);
      setShowMention(false);
      setSlashFilter(nextValue.slice(1).toLowerCase());
      setSelectedIdx(0);
      return;
    }

    const mentionFilterValue = mentionFilterFromInput(nextValue);
    if (mentionFilterValue !== null && mentionFilterValue.length < 15) {
      setShowMention(true);
      setShowSlash(false);
      setMentionFilter(mentionFilterValue);
      setSelectedIdx(0);
      return;
    }

    closePopups();
  }

  function selectCommand(command) {
    setValue(`${command.cmd} `);
    setShowSlash(false);
    focusInput();
  }

  function selectMention(agent) {
    const parts = value.split("@");
    parts.pop();
    const mentionValue = agent === "all" ? "all" : agent;
    setValue(`${parts.join("@")}@${mentionValue} `);
    setShowMention(false);
    focusInput();
  }

  function handleSubmit() {
    const trimmed = value.trim();
    if (!trimmed) {
      return;
    }

    if (onSendMessage) {
      onSendMessage(trimmed);
    }

    setValue("");
    closePopups();
    setSelectedIdx(0);
  }

  function handleKeyDown(event) {
    if (showSlash) {
      if (!filteredCommands.length) {
        if (event.key === "Escape") {
          setShowSlash(false);
          return;
        }
        // fall through so Enter can reach submit logic below
      } else {
        if (event.key === "ArrowDown") {
          event.preventDefault();
          setSelectedIdx((prev) => Math.min(prev + 1, filteredCommands.length - 1));
        } else if (event.key === "ArrowUp") {
          event.preventDefault();
          setSelectedIdx((prev) => Math.max(prev - 1, 0));
        } else if (event.key === "Tab" || event.key === "Enter") {
          event.preventDefault();
          if (filteredCommands[selectedIdx]) {
            selectCommand(filteredCommands[selectedIdx]);
          }
        } else if (event.key === "Escape") {
          setShowSlash(false);
        }
        return;
      }
    }

    if (showMention) {
      const hasAll = "all".includes(mentionFilter);
      const totalItems = filteredMentions.length + (hasAll ? 1 : 0);
      if (!totalItems) {
        if (event.key === "Escape") {
          setShowMention(false);
          return;
        }
        // fall through so Enter can reach submit logic below
      } else {
        if (event.key === "ArrowDown") {
          event.preventDefault();
          setSelectedIdx((prev) => Math.min(prev + 1, totalItems - 1));
        } else if (event.key === "ArrowUp") {
          event.preventDefault();
          setSelectedIdx((prev) => Math.max(prev - 1, 0));
        } else if (event.key === "Tab" || event.key === "Enter") {
          event.preventDefault();
          if (hasAll && selectedIdx === 0) {
            selectMention("all");
          } else {
            const mentionIndex = hasAll ? selectedIdx - 1 : selectedIdx;
            if (filteredMentions[mentionIndex]) {
              selectMention(filteredMentions[mentionIndex][0]);
            }
          }
        } else if (event.key === "Escape") {
          setShowMention(false);
        }
        return;
      }
    }

    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  }

  const hasAllRow = "all".includes(mentionFilter);
  const popupOpen = showSlash || showMention;

  return (
    <div className={styles.wrapper}>
      {replyMessage && (
        <div className={styles.replyContext}>
          <div className={styles.replyText}>
            Replying to <strong>{replyMessage.sender}</strong>: {String(replyMessage.content || replyMessage.text || '').slice(0, 80)}
          </div>
          <button type="button" className={styles.replyClose} onClick={onCancelReply} aria-label="Dismiss reply context">
            ×
          </button>
        </div>
      )}

      {showSlash && filteredCommands.length > 0 ? (
        <div className={`${styles.popup} ${styles.slashPopup}`}>
          <div className={`${styles.popupHeader} ${styles.sticky}`}>Commands</div>
          {filteredCommands.map((command, index) => (
            <div
              key={command.cmd}
              className={styles.row}
              onClick={() => selectCommand(command)}
              onMouseEnter={() => setSelectedIdx(index)}
              style={{
                background: index === selectedIdx ? "rgba(168, 85, 247, 0.071)" : "transparent",
                borderLeftColor: index === selectedIdx ? "var(--purple)" : "transparent",
              }}
            >
              <span className={styles.commandText}>{command.cmd}</span>
              <span className={styles.description}>{command.desc}</span>
            </div>
          ))}
        </div>
      ) : null}

      {showMention && (filteredMentions.length > 0 || hasAllRow) ? (
        <div className={`${styles.popup} ${styles.mentionPopup}`}>
          <div className={styles.popupHeader}>Mention an Agent</div>
          {hasAllRow ? (
            <div
              className={`${styles.row} ${styles.mentionRow}`}
              onClick={() => selectMention("all")}
              onMouseEnter={() => setSelectedIdx(0)}
              style={{
                background: selectedIdx === 0 ? "rgba(168, 85, 247, 0.063)" : "transparent",
                borderLeftColor: selectedIdx === 0 ? "var(--purple)" : "transparent",
                borderBottom: "1px solid rgba(31, 41, 55, 0.251)",
              }}
            >
              <div
                className={styles.avatar}
                style={{
                  background: "rgba(168, 85, 247, 0.082)",
                  border: "1px solid rgba(168, 85, 247, 0.251)",
                }}
              >
                <UsersIcon size={13} color="var(--purple)" />
              </div>
              <span className={styles.mentionLabel} style={{ color: "var(--purple)", fontWeight: 600 }}>
                @all
              </span>
              <span className={styles.mentionDesc}>All agents in channel</span>
            </div>
          ) : null}

          {filteredMentions.map(([key, meta], index) => {
            const rowIndex = hasAllRow ? index + 1 : index;
            return (
              <div
                key={key}
                className={`${styles.row} ${styles.mentionRow}`}
                onClick={() => selectMention(key)}
                onMouseEnter={() => setSelectedIdx(rowIndex)}
                style={{
                  background: rowIndex === selectedIdx ? `${meta.color}10` : "transparent",
                  borderLeftColor: rowIndex === selectedIdx ? meta.color : "transparent",
                }}
              >
                <div
                  className={styles.avatar}
                  style={{
                    background: `${meta.color}15`,
                    border: `1px solid ${meta.color}40`,
                  }}
                >
                  <AgentLogo agent={key} size={14} />
                </div>
                <span className={styles.mentionLabel} style={{ color: meta.color }}>
                  @{meta.label}
                </span>
                <span className={styles.mentionDesc}>AI Agent</span>
              </div>
            );
          })}
        </div>
      ) : null}

      <div className={`${styles.bar} ${popupOpen ? styles.barOpen : ""}`.trim()}>
        <textarea
          ref={inputRef}
          className={styles.input}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Type a message... (use @name to mention agents)"
          rows={1}
        />
        <ToolbarBtn title="Voice">
          <MicIcon size={14} color="currentColor" />
        </ToolbarBtn>
        <button type="button" className={styles.sendBtn} onClick={handleSubmit}>
          <div className={styles.sendShimmer} />
          <span className={styles.sendInner}>
            <BoltIcon size={15} color="#FFFFFF" glow={false} />
            SEND
          </span>
        </button>
        <ToolbarBtn title="Schedule" onClick={onSchedule}>
          <ClockIcon size={14} color="currentColor" />
        </ToolbarBtn>
      </div>

      <div className={styles.helper}>
        Enter to send · Shift+Enter for newline · Type{" "}
        <span className={styles.hint}>/</span> or <span className={styles.hint}>@</span> for autocomplete
      </div>
    </div>
  );
}
