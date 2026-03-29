import { useEffect, useMemo, useRef, useState } from "react";
import {
  createChannel,
  getChannel,
  getChannelAgents,
  getChannelMessages,
  getChannels,
  getChannelTriggers,
  sendChannelMessage,
} from "./api";
import { createWsClient } from "../../api/ws";
import { mockMessagesByChannelId } from "./mockData";
import AgentRuntimeStrip from "./components/AgentRuntimeStrip";
import ChannelCreateModal from "./components/ChannelCreateModal";
import ChannelHeader from "./components/ChannelHeader";
import ChatShell from "./components/ChatShell";
import RuntimeDetailsPanel from "./components/RuntimeDetailsPanel";
import SidebarChannelList from "./components/SidebarChannelList";
import TriggerSummary from "./components/TriggerSummary";
import "./channelShell.css";

function normalizeChannels(data) {
  if (!Array.isArray(data)) return [];
  return data.map((item, index) => ({
    id: item.id || `channel-${index}`,
    name: item.name || "channel",
    type: item.type === "repo" ? "repo" : "general",
    repo_path: item.repo_path || null,
    unread_count: Number.isFinite(Number(item.unread_count)) ? Number(item.unread_count) : 0,
  }));
}

function normalizeAgents(data, channelId) {
  if (!Array.isArray(data)) return [];
  return data.map((agent, index) => ({
    id: agent.id || `${channelId || "channel"}:${agent.agent_type || agent.name || index}`,
    channel_id: agent.channel_id || channelId || "",
    agent_type: String(agent.agent_type || agent.name || "unknown").toLowerCase(),
    status: agent.status === "working" ? "working" : agent.status === "idle" ? "idle" : "offline",
    current_task: agent.current_task || null,
    last_response_time: agent.last_response_time || agent.last_activity || null,
    last_heartbeat: agent.last_heartbeat || agent.last_activity || null,
    last_error: agent.last_error || null,
    open_trigger_count: Number.isFinite(Number(agent.open_trigger_count))
      ? Number(agent.open_trigger_count)
      : null,
  }));
}

function formatClockTime(value) {
  if (value === null || value === undefined || value === "") return "--";
  if (typeof value === "number" && Number.isFinite(value)) {
    return new Date(value * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  if (typeof value === "string") {
    const asNumber = Number(value);
    if (Number.isFinite(asNumber)) {
      return new Date(asNumber * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
    return value;
  }
  return "--";
}

function normalizeTriggers(data, channelId) {
  if (!Array.isArray(data)) return [];
  return data.map((trigger, index) => ({
    id: trigger.id || `trigger-${index}`,
    channel_id: trigger.channel_id || channelId || "",
    target: String(trigger.target || trigger.agent_type || "").toLowerCase(),
    state: String(trigger.state || "pending").toLowerCase(),
    last_error: trigger.last_error || null,
    created_at: trigger.created_at || null,
    completed_at: trigger.completed_at || null,
  }));
}

function normalizeMessages(data, channelId) {
  if (!Array.isArray(data)) return [];
  return data.map((message, index) => {
    const senderRaw = String(message.sender || "system");
    const senderLower = senderRaw.toLowerCase();
    const isAssistant = senderLower === "claude" || senderLower === "codex" || senderLower === "gemini";
    const sender =
      senderLower === "human"
        ? "You"
        : senderLower === "system"
          ? "System"
          : senderRaw.slice(0, 1).toUpperCase() + senderRaw.slice(1);

    return {
      id: message.id || `${channelId || "channel"}-msg-${index}`,
      sender,
      sender_type: isAssistant ? "assistant" : senderLower === "system" ? "system" : "user",
      text: message.text || "",
      time: formatClockTime(message.timestamp ?? message.time),
    };
  });
}

function summarizeTriggers(triggers) {
  return triggers.reduce(
    (acc, trigger) => {
      if (trigger.state === "pending") acc.pending += 1;
      if (trigger.state === "claimed" || trigger.state === "working") acc.working += 1;
      if (trigger.state === "completed") acc.completed += 1;
      if (trigger.state === "failed") acc.failed += 1;
      return acc;
    },
    { pending: 0, working: 0, completed: 0, failed: 0 },
  );
}

function computeOpenByAgent(triggers) {
  const counts = {};
  for (const trigger of triggers) {
    if (trigger.state !== "pending" && trigger.state !== "claimed" && trigger.state !== "working") continue;
    const target = trigger.target || "unknown";
    counts[target] = (counts[target] || 0) + 1;
  }
  return counts;
}

function mergeRuntimeAgents(agents, openByAgent) {
  return agents.map((agent) => {
    const triggerDerivedCount = openByAgent[agent.agent_type];
    const backendCount = Number(agent.open_trigger_count);
    const open_trigger_count = Number.isFinite(triggerDerivedCount)
      ? triggerDerivedCount
      : Number.isFinite(backendCount)
        ? backendCount
        : 0;

    return {
      ...agent,
      open_trigger_count,
    };
  });
}

const WS_URL = (import.meta.env.VITE_API_BASE ?? "http://localhost:8000")
  .replace(/\/$/, "")
  .replace(/^http/, "ws") + "/ws";

export default function ChannelShell() {
  const [channels, setChannels] = useState([]);
  const [activeChannelId, setActiveChannelId] = useState(null);
  const [activeChannel, setActiveChannel] = useState(null);
  const [agents, setAgents] = useState([]);
  const [triggers, setTriggers] = useState([]);
  const [channelError, setChannelError] = useState(null);
  const [agentError, setAgentError] = useState(null);
  const [triggerError, setTriggerError] = useState(null);
  const [messagesError, setMessagesError] = useState(null);
  const [messagesByChannelId, setMessagesByChannelId] = useState(mockMessagesByChannelId);
  const [createOpen, setCreateOpen] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const activeChannelIdRef = useRef(null);

  useEffect(() => {
    let ignore = false;

    async function loadChannels() {
      const result = normalizeChannels(await getChannels());
      if (ignore) return;
      setChannels(result);
      if (result.length > 0) {
        setActiveChannelId(result[0].id);
      }
    }

    loadChannels();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    if (!activeChannelId) return undefined;

    setActiveChannel(null);
    setAgents([]);
    setTriggers([]);
    setChannelError(null);
    setAgentError(null);
    setTriggerError(null);
    setMessagesError(null);
    setMessagesByChannelId((prev) => ({
      ...prev,
      [activeChannelId]: [],
    }));
    return undefined;
  }, [activeChannelId]);

  // Keep activeChannelId in a ref so the WebSocket handler can read it
  // without being a dependency of the WS effect.
  useEffect(() => {
    activeChannelIdRef.current = activeChannelId;
  }, [activeChannelId]);

  // Load channel context via REST on channel switch (initial history load).
  useEffect(() => {
    let ignore = false;
    if (!activeChannelId) return undefined;

    async function loadChannelContext() {
      const [channelResult, agentsResult, triggersResult, messagesResult] = await Promise.allSettled([
        getChannel(activeChannelId),
        getChannelAgents(activeChannelId),
        getChannelTriggers(activeChannelId),
        getChannelMessages(activeChannelId),
      ]);
      if (ignore) return;

      if (channelResult.status === "fulfilled") {
        setActiveChannel(channelResult.value);
        setChannelError(null);
      } else {
        setActiveChannel(null);
        setChannelError("Channel metadata unavailable");
      }

      if (agentsResult.status === "fulfilled") {
        setAgents(normalizeAgents(agentsResult.value, activeChannelId));
        setAgentError(null);
      } else {
        setAgents([]);
        setAgentError("Runtime agent state unavailable");
      }

      if (triggersResult.status === "fulfilled") {
        setTriggers(normalizeTriggers(triggersResult.value, activeChannelId));
        setTriggerError(null);
      } else {
        setTriggers([]);
        setTriggerError("Trigger data unavailable");
      }

      if (messagesResult.status === "fulfilled") {
        const normalized = normalizeMessages(messagesResult.value, activeChannelId);
        setMessagesByChannelId((prev) => ({
          ...prev,
          [activeChannelId]: normalized,
        }));
        setMessagesError(null);
      } else {
        setMessagesByChannelId((prev) => ({
          ...prev,
          [activeChannelId]: [],
        }));
        setMessagesError("Messages unavailable");
      }
    }

    loadChannelContext();
    return () => {
      ignore = true;
    };
  }, [activeChannelId]);

  // WebSocket connection for real-time updates (replaces 3-second polling).
  useEffect(() => {
    function handleWsEvent(event) {
      const channelId = activeChannelIdRef.current;

      if (event.type === "new_message" && event.message) {
        const msgChannelId = event.message.channel || event.message.channel_id;
        if (msgChannelId && msgChannelId === channelId) {
          const normalized = normalizeMessages([event.message], channelId);
          setMessagesByChannelId((prev) => {
            const existing = prev[channelId] || [];
            const deduped = normalized.filter(
              (msg) => !existing.some((e) => e.id === msg.id),
            );
            if (deduped.length === 0) return prev;
            return { ...prev, [channelId]: [...existing, ...deduped] };
          });
        }
      }

      if (event.type === "trigger_state_change" && event.trigger_id) {
        setTriggers((prev) =>
          prev.map((t) => (t.id === event.trigger_id ? { ...t, state: event.state } : t)),
        );
      }

      if (event.type === "agent_status_change" && event.agent_id) {
        setAgents((prev) =>
          prev.map((a) => (a.id === event.agent_id ? { ...a, status: event.status } : a)),
        );
      }
    }

    const client = createWsClient(WS_URL, handleWsEvent, setWsConnected);
    return () => client.close();
  }, []);

  const activeMessages = useMemo(
    () => (activeChannelId ? messagesByChannelId[activeChannelId] || [] : []),
    [activeChannelId, messagesByChannelId],
  );
  const triggerSummary = useMemo(() => summarizeTriggers(triggers), [triggers]);
  const openByAgent = useMemo(() => computeOpenByAgent(triggers), [triggers]);
  const mergedAgents = useMemo(() => mergeRuntimeAgents(agents, openByAgent), [agents, openByAgent]);
  const runtimeAgentMap = useMemo(() => {
    const map = {};
    for (const agent of mergedAgents) {
      map[agent.agent_type] = {
        ...agent,
      };
    }
    return map;
  }, [mergedAgents]);
  const hasRuntimeData = mergedAgents.length > 0 || triggers.length > 0;
  const claudeRuntime = runtimeAgentMap.claude || null;
  const isClaudeWorking = claudeRuntime?.status === "working";
  const latestClaudeFailure = useMemo(() => {
    const claudeTriggers = triggers
      .filter((trigger) => trigger.target === "claude")
      .sort((a, b) => Number(b.completed_at || b.created_at || 0) - Number(a.completed_at || a.created_at || 0));
    if (claudeTriggers.length === 0) return null;
    const latest = claudeTriggers[0];
    if (latest.state !== "failed" || !latest.last_error) return null;
    const text = String(latest.last_error || "")
      .replace(/traceback[\s\S]*/i, "")
      .split("\n")[0]
      .trim();
    return text ? text.slice(0, 180) : "Runner error";
  }, [triggers]);

  const onCreate = async (payload) => {
    const created = await createChannel(payload);
    const normalized = normalizeChannels([created])[0];
    setChannels((prev) => [...prev, normalized]);
    setActiveChannelId(normalized.id);
    setCreateOpen(false);
  };

  const onSend = (text) => {
    if (!activeChannelId) {
      return Promise.reject(new Error("No active channel selected"));
    }
    return sendChannelMessage({ channelId: activeChannelId, text, sender: "human" }).catch(
      (error) => {
        console.error("Failed to send message:", error);
        setMessagesError("Failed to send message");
        throw error;
      },
    );
  };

  const showChannel = activeChannel || channels.find((channel) => channel.id === activeChannelId) || null;

  return (
    <div className="channel-shell-layout">
      <SidebarChannelList
        channels={channels}
        activeChannelId={activeChannelId}
        onSelect={setActiveChannelId}
        onOpenCreate={() => setCreateOpen(true)}
      />

      <main className="channel-shell-main">
        <div className={`ws-status ${wsConnected ? "ws-status--connected" : "ws-status--reconnecting"}`}>
          <span className="ws-status__dot" />
          {wsConnected ? "Connected" : "Reconnecting\u2026"}
        </div>
        <ChannelHeader channel={showChannel} runtimeStrip={<AgentRuntimeStrip agentMap={runtimeAgentMap} />} />
        {channelError ? <div className="channel-header-error">{channelError}</div> : null}
        <TriggerSummary summary={triggerSummary} hasData={hasRuntimeData} error={triggerError} />
        <RuntimeDetailsPanel channelId={activeChannelId} agents={mergedAgents} error={agentError} />
        <ChatShell
          channel={showChannel}
          messages={activeMessages}
          onSend={onSend}
          messageError={messagesError}
          claudeWorking={isClaudeWorking}
          claudeFailure={latestClaudeFailure}
        />
      </main>

      <ChannelCreateModal open={createOpen} onClose={() => setCreateOpen(false)} onCreate={onCreate} />
    </div>
  );
}
