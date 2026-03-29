import { useEffect, useMemo, useState } from "react";
import { createChannel, getChannel, getChannelAgents, getChannels, getChannelTriggers } from "./api";
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

function normalizeTriggers(data, channelId) {
  if (!Array.isArray(data)) return [];
  return data.map((trigger, index) => ({
    id: trigger.id || `trigger-${index}`,
    channel_id: trigger.channel_id || channelId || "",
    target: String(trigger.target || trigger.agent_type || "").toLowerCase(),
    state: String(trigger.state || "pending").toLowerCase(),
  }));
}

function summarizeTriggers(triggers) {
  return triggers.reduce(
    (acc, trigger) => {
      if (trigger.state === "pending") acc.pending += 1;
      if (trigger.state === "claimed") acc.claimed += 1;
      if (trigger.state === "failed") acc.failed += 1;
      return acc;
    },
    { pending: 0, claimed: 0, failed: 0 },
  );
}

function computeOpenByAgent(triggers) {
  const counts = {};
  for (const trigger of triggers) {
    if (trigger.state !== "pending" && trigger.state !== "claimed") continue;
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
export default function ChannelShell() {
  const [channels, setChannels] = useState([]);
  const [activeChannelId, setActiveChannelId] = useState(null);
  const [activeChannel, setActiveChannel] = useState(null);
  const [agents, setAgents] = useState([]);
  const [triggers, setTriggers] = useState([]);
  const [channelError, setChannelError] = useState(null);
  const [agentError, setAgentError] = useState(null);
  const [triggerError, setTriggerError] = useState(null);
  const [messagesByChannelId, setMessagesByChannelId] = useState(mockMessagesByChannelId);
  const [createOpen, setCreateOpen] = useState(false);

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
    let ignore = false;
    if (!activeChannelId) return undefined;

    async function loadChannelContext() {
      setChannelError(null);
      setAgentError(null);
      setTriggerError(null);
      setActiveChannel(null);
      setAgents([]);
      setTriggers([]);
      const [channelResult, agentsResult, triggersResult] = await Promise.allSettled([
        getChannel(activeChannelId),
        getChannelAgents(activeChannelId),
        getChannelTriggers(activeChannelId),
      ]);
      if (ignore) return;

      if (channelResult.status === "fulfilled") {
        setActiveChannel(channelResult.value);
      } else {
        setActiveChannel(null);
        setChannelError("Backend unavailable");
      }

      if (agentsResult.status === "fulfilled") {
        setAgents(normalizeAgents(agentsResult.value, activeChannelId));
      } else {
        setAgents([]);
        setAgentError("Runtime agent state unavailable");
      }

      if (triggersResult.status === "fulfilled") {
        setTriggers(normalizeTriggers(triggersResult.value, activeChannelId));
      } else {
        setTriggers([]);
        setTriggerError("Trigger data unavailable");
      }
    }

    loadChannelContext();
    return () => {
      ignore = true;
    };
  }, [activeChannelId]);

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

  const onCreate = async (payload) => {
    const created = await createChannel(payload);
    const normalized = normalizeChannels([created])[0];
    setChannels((prev) => [...prev, normalized]);
    setActiveChannelId(normalized.id);
    setCreateOpen(false);
  };

  const onSend = (text) => {
    if (!activeChannelId) return;
    const entry = {
      id: `local-msg-${Date.now()}`,
      sender: "You",
      text,
      time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };
    setMessagesByChannelId((prev) => ({
      ...prev,
      [activeChannelId]: [...(prev[activeChannelId] || []), entry],
    }));
  };

  return (
    <div className="channel-shell-layout">
      <SidebarChannelList
        channels={channels}
        activeChannelId={activeChannelId}
        onSelect={setActiveChannelId}
        onOpenCreate={() => setCreateOpen(true)}
      />

      <main className="channel-shell-main">
        <ChannelHeader channel={activeChannel} runtimeStrip={<AgentRuntimeStrip agentMap={runtimeAgentMap} />} />
        {channelError ? <div className="channel-header-error">{channelError}</div> : null}
        <TriggerSummary summary={triggerSummary} hasData={hasRuntimeData} error={triggerError} />
        <RuntimeDetailsPanel channelId={activeChannelId} agents={mergedAgents} error={agentError} />
        <ChatShell channel={activeChannel} messages={activeMessages} onSend={onSend} />
      </main>

      <ChannelCreateModal open={createOpen} onClose={() => setCreateOpen(false)} onCreate={onCreate} />
    </div>
  );
}
