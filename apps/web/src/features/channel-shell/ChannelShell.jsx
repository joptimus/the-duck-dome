import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  addChannelAgent,
  createChannel,
  createJob,
  deleteChannelMessage,
  deregisterRuntimeAgent,
  triggerAgent,
  getChannel,
  getChannelAgents,
  getJobs,
  getChannelMessages,
  getPendingToolRequests,
  getChannels,
  getChannelTriggers,
  registerRuntimeAgent,
  removeChannelAgent,
  sendChannelMessage,
  getRepos,
  addRepoSource,
  removeRepoSource,
  approveToolRequest,
  denyToolRequest,
  bootChannel,
} from "./api";
import { createWsClient } from "../../api/ws";
import { mockMessagesByChannelId } from "./mockData";
import { AppShell } from "../../components/layout/AppShell";
import { Sidebar } from "../../components/sidebar/Sidebar";
import { TopBar } from "../../components/topbar/TopBar";
import { ChatTimeline } from "../../components/chat/ChatTimeline";
import { Composer } from "../../components/chat/Composer";
import { AgentThinkingStrip } from "../../components/chat/AgentThinkingStrip";
import { ActivityPanel, AgentsPanel, JobsPanel, RulesPanel, SettingsPanel } from "../../components/panels";
import { SessionLauncher } from "../../components/modals/SessionLauncher";
import { ScheduleModal } from "../../components/modals/ScheduleModal";
import CreateChannelModal from "../../components/modals/CreateChannelModal";

const PINNED_MESSAGES_STORAGE_KEY = "duckdome.pinnedMessages";

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

function normalizeFsPath(path) {
  return String(path || "")
    .trim()
    .replace(/\\/g, "/")
    .replace(/\/+$/g, "")
    .toLowerCase();
}

function slugifyName(value) {
  return String(value || "")
    .toLowerCase()
    .trim()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "");
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
    pid: agent.pid || null,
    started_at: agent.started_at || null,
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
    const messageType = String(message.type || "").toLowerCase();
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
      sender_type:
        message.sender_type ||
        (messageType === "system"
          ? "system"
          : isAssistant
            ? "assistant"
            : senderLower === "system"
              ? "system"
              : "user"),
      type: messageType || undefined,
      subtype: message.subtype || undefined,
      agent: message.agent || undefined,
      text: message.text || "",
      content: message.content || message.text || "",
      channel: message.channel || message.channel_id || channelId || "",
      reply_to: message.reply_to || null,
      time: formatClockTime(message.timestamp ?? message.time),
      timestamp: message.timestamp ?? message.time,
    };
  });
}

function normalizeJobs(data) {
  if (!Array.isArray(data)) return [];
  return data.map((job) => ({
    id: String(job.id || ""),
    title: String(job.title || "Untitled job"),
    body: String(job.body || ""),
    channel: String(job.channel || ""),
    status: String(job.status || "open").toLowerCase(),
  }));
}

function decorateMessages(messages) {
  const byId = new Map(messages.map((message) => [message.id, message]));
  return messages.map((message) => {
    if (!message.reply_to) return message;
    const target = byId.get(message.reply_to);
    return {
      ...message,
      reply_preview: target
        ? {
            id: target.id,
            sender: target.sender,
            text: String(target.content || target.text || "").slice(0, 120),
          }
        : {
            id: message.reply_to,
            sender: "Message",
            text: "",
          },
    };
  });
}

function loadPinnedMessages() {
  if (typeof window === "undefined") return {};
  try {
    const parsed = JSON.parse(window.localStorage.getItem(PINNED_MESSAGES_STORAGE_KEY) || "{}");
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    const result = {};
    for (const [key, value] of Object.entries(parsed)) {
      if (Array.isArray(value)) result[key] = value;
    }
    return result;
  } catch {
    return {};
  }
}

function formatApprovalTime(value) {
  if (value === null || value === undefined || value === "") return "--";
  const asNumber = Number(value);
  if (!Number.isFinite(asNumber)) return String(value);
  return formatClockTime(asNumber);
}

function normalizeApprovalMessages(data, channelId) {
  if (!Array.isArray(data)) return [];
  return data.map((approval, index) => ({
    id: approval.id || `${channelId || "channel"}-approval-${index}`,
    type: "tool_approval",
    sender: String(approval.agent || "system"),
    sender_type: "tool_approval",
    status: String(approval.status || "pending").toLowerCase(),
    agent: String(approval.agent || ""),
    tool: String(approval.tool || ""),
    command: formatApprovalCommand(approval.tool, approval.arguments),
    reason: `${approval.agent} wants to use ${approval.tool}`,
    diff: extractApprovalDiff(approval.tool, approval.arguments),
    time: formatApprovalTime(approval.created_at),
    resolvedAt: approval.resolved_at ? formatApprovalTime(approval.resolved_at) : null,
    resolvedBy: approval.resolved_by || null,
    channel: approval.channel || channelId || "",
    timestamp: approval.created_at ?? null,
  }));
}

function mergeChannelTimeline(historyMessages, approvalMessages, existingMessages = []) {
  const approvalById = new Map();

  for (const msg of existingMessages) {
    if (msg.type === "tool_approval") {
      approvalById.set(msg.id, msg);
    }
  }

  for (const msg of approvalMessages) {
    approvalById.set(msg.id, msg);
  }

  const merged = [...historyMessages];
  for (const approval of approvalById.values()) {
    if (!merged.some((msg) => msg.id === approval.id)) {
      merged.push(approval);
    }
  }

  merged.sort((a, b) => Number(a.timestamp || 0) - Number(b.timestamp || 0));
  return merged;
}

function formatApprovalCommand(tool, args) {
  const normalizedTool = String(tool || "").toLowerCase();
  const params = args && typeof args === "object" ? args : {};

  if (typeof params.command === "string" && params.command.trim()) return params.command;
  if (typeof params.cmd === "string" && params.cmd.trim()) return params.cmd;
  if (typeof params.path === "string" && params.path.trim()) {
    if (normalizedTool === "write_file") return params.path;
    return `${normalizedTool || "tool"} ${params.path}`;
  }

  const serialized = JSON.stringify(params);
  return serialized === "{}" ? normalizedTool : serialized;
}

function extractApprovalDiff(tool, args) {
  const normalizedTool = String(tool || "").toLowerCase();
  if (normalizedTool !== "write_file") return null;
  const params = args && typeof args === "object" ? args : {};
  const content = typeof params.content === "string" ? params.content : "";
  if (!content) return null;
  const lineCount = content.split(/\r?\n/).length;
  return `+${lineCount} lines`;
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

function extractMentionTargets(text, availableAgents = []) {
  const tags = String(text || "")
    .toLowerCase()
    .match(/@([a-z0-9_-]+)/g) || [];
  if (tags.length === 0) return [];

  const mentions = tags.map((tag) => tag.slice(1));
  const unique = [];
  const seen = new Set();

  for (const mention of mentions) {
    if (mention === "all") {
      for (const agent of availableAgents) {
        if (!seen.has(agent)) {
          seen.add(agent);
          unique.push(agent);
        }
      }
      continue;
    }

    if (availableAgents.includes(mention) && !seen.has(mention)) {
      seen.add(mention);
      unique.push(mention);
    }
  }

  return unique;
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
  const [repos, setRepos] = useState([]);
  const [activeChannelId, setActiveChannelId] = useState(null);
  const [activeChannel, setActiveChannel] = useState(null);
  const [agents, setAgents] = useState([]);
  const [triggers, setTriggers] = useState([]);
  const [channelError, setChannelError] = useState(null);
  const [agentError, setAgentError] = useState(null);
  const [triggerError, setTriggerError] = useState(null);
  const [messagesError, setMessagesError] = useState(null);
  const [messagesByChannelId, setMessagesByChannelId] = useState(mockMessagesByChannelId);
  const [jobsByChannelId, setJobsByChannelId] = useState({});
  const [replyingTo, setReplyingTo] = useState(null);
  const [pinnedByChannelId, setPinnedByChannelId] = useState(() => loadPinnedMessages());
  const [createOpen, setCreateOpen] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const activeChannelIdRef = useRef(null);

  // New UI state
  const [activePanel, setActivePanel] = useState(null);
  const [sessionLauncherOpen, setSessionLauncherOpen] = useState(false);
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false);

  const fetchRepos = useCallback(async () => {
    try {
      const data = await getRepos();
      const repoList = Array.isArray(data) ? data : data?.repos ?? [];
      setRepos(
        repoList.map((r) => ({
          name: r.name,
          path: r.path,
          active: false,
        }))
      );
    } catch {
      // API unavailable — keep current list
    }
  }, []);

  const handleAddRepo = useCallback(async (path) => {
    await addRepoSource(path);
    await fetchRepos();
  }, [fetchRepos]);

  const handleRemoveRepo = useCallback(async (path) => {
    await removeRepoSource(path);
    await fetchRepos();
  }, [fetchRepos]);

  const handleBrowseRepo = useCallback(async () => {
    if (window.duckdome?.pickDirectory) {
      const result = await window.duckdome.pickDirectory();
      if (!result.canceled && result.path) return result.path;
      return null;
    }
    const entered = window.prompt('Enter absolute path to repo:') ?? '';
    return entered.trim() || null;
  }, []);

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
    fetchRepos();
    return () => {
      ignore = true;
    };
  }, [fetchRepos]);

  useEffect(() => {
    if (!activeChannelId) return undefined;

    setActiveChannel(null);
    setAgents([]);
    setTriggers([]);
    setReplyingTo(null);
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
      const [channelResult, agentsResult, triggersResult, messagesResult, approvalsResult, jobsResult] = await Promise.allSettled([
        getChannel(activeChannelId),
        getChannelAgents(activeChannelId),
        getChannelTriggers(activeChannelId),
        getChannelMessages(activeChannelId),
        getPendingToolRequests(activeChannelId),
        getJobs(activeChannelId),
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
        const approvalMessages =
          approvalsResult.status === "fulfilled"
            ? normalizeApprovalMessages(approvalsResult.value, activeChannelId)
            : [];
        setMessagesByChannelId((prev) => ({
          ...prev,
          [activeChannelId]: decorateMessages(
            mergeChannelTimeline(
              normalized,
              approvalMessages,
              prev[activeChannelId] || [],
            ),
          ),
        }));
        setMessagesError(null);
      } else {
        setMessagesByChannelId((prev) => ({
          ...prev,
          [activeChannelId]: [],
        }));
        setMessagesError("Messages unavailable");
      }

      if (jobsResult.status === "fulfilled") {
        setJobsByChannelId((prev) => ({
          ...prev,
          [activeChannelId]: normalizeJobs(jobsResult.value),
        }));
      }
    }

    loadChannelContext().then(async () => {
      if (!activeChannelId || ignore) return;
      // Boot agents for this channel after context is loaded.
      try {
        await bootChannel(activeChannelId);
      } catch {}
      // Re-fetch agents to pick up newly registered + working status.
      if (!ignore) {
        try {
          const refreshed = await getChannelAgents(activeChannelId);
          setAgents(normalizeAgents(refreshed, activeChannelId));
        } catch {}
      }
    });
    return () => {
      ignore = true;
    };
  }, [activeChannelId]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(PINNED_MESSAGES_STORAGE_KEY, JSON.stringify(pinnedByChannelId));
  }, [pinnedByChannelId]);

  // WebSocket connection for real-time updates (replaces 3-second polling).
  useEffect(() => {
    function handleWsEvent(event) {
      const channelId = activeChannelIdRef.current;

      if (event.type === "new_message" && event.message) {
        const msgChannelId = event.message.channel || event.message.channel_id;
        if (msgChannelId && msgChannelId === channelId) {
          const normalized = normalizeMessages([event.message], channelId);
          setMessagesByChannelId((prev) => {
            let existing = prev[channelId] || [];
            // Replace optimistic messages from the same sender with the real one.
            const realMsg = normalized[0];
            if (realMsg) {
              existing = existing.filter((e) => !e.id.startsWith("optimistic-") || e.sender !== realMsg.sender);
            }
            const deduped = normalized.filter(
              (msg) => !existing.some((e) => e.id === msg.id),
            );
            if (deduped.length === 0) return prev;
            return { ...prev, [channelId]: decorateMessages([...existing, ...deduped]) };
          });
        }
      }

      if (event.type === "message_deleted" && event.message_id && event.channel) {
        setMessagesByChannelId((prev) => {
          const existing = prev[event.channel] || [];
          return {
            ...prev,
            [event.channel]: decorateMessages(existing.filter((message) => message.id !== event.message_id)),
          };
        });
        setPinnedByChannelId((prev) => {
          const existing = prev[event.channel] || [];
          if (!existing.includes(event.message_id)) return prev;
          return { ...prev, [event.channel]: existing.filter((id) => id !== event.message_id) };
        });
        setReplyingTo((prev) => (prev?.id === event.message_id ? null : prev));
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

      if (event.type === "tool_approval_updated" && event.approval) {
        const approval = event.approval;
        const approvalChannel = approval.channel;
        const approvalMsg = normalizeApprovalMessages([approval], approvalChannel)[0];
        setMessagesByChannelId((prev) => {
          const existing = prev[approvalChannel] || [];
          const idx = existing.findIndex((m) => m.id === approval.id);
          if (idx >= 0) {
            // Update existing approval message
            const updated = [...existing];
            updated[idx] = approvalMsg;
            return { ...prev, [approvalChannel]: decorateMessages(updated) };
          }
          // Add new approval message
          return { ...prev, [approvalChannel]: decorateMessages([...existing, approvalMsg]) };
        });
      }

      if (event.type === "job_updated" && event.job) {
        const normalizedJob = normalizeJobs([event.job])[0];
        if (!normalizedJob?.channel) return;
        setJobsByChannelId((prev) => {
          const existing = prev[normalizedJob.channel] || [];
          const next = existing.filter((job) => job.id !== normalizedJob.id);
          return {
            ...prev,
            [normalizedJob.channel]: [normalizedJob, ...next],
          };
        });
      }
    }

    const client = createWsClient(WS_URL, handleWsEvent, setWsConnected);
    return () => client.close();
  }, []);

  const activeMessages = useMemo(
    () => (activeChannelId ? messagesByChannelId[activeChannelId] || [] : []),
    [activeChannelId, messagesByChannelId],
  );
  const activeJobs = useMemo(
    () => (activeChannelId ? jobsByChannelId[activeChannelId] || [] : []),
    [activeChannelId, jobsByChannelId],
  );
  const pinnedMessages = useMemo(() => {
    if (!activeChannelId) return [];
    const pinnedIds = pinnedByChannelId[activeChannelId] || [];
    return pinnedIds
      .map((id) => activeMessages.find((message) => message.id === id))
      .filter(Boolean)
      .map((message) => ({
        id: message.id,
        sender: message.sender,
        text: String(message.content || message.text || "").slice(0, 140),
      }));
  }, [activeChannelId, activeMessages, pinnedByChannelId]);
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
  const latestAgentFailure = useMemo(() => {
    const failedTriggers = triggers
      .filter((trigger) => trigger.state === "failed" && trigger.last_error)
      .sort((a, b) => Number(b.completed_at || b.created_at || 0) - Number(a.completed_at || a.created_at || 0));
    if (failedTriggers.length === 0) return null;
    const latest = failedTriggers[0];
    const agent = latest.target || "agent";
    const text = String(latest.last_error || "")
      .replace(/traceback[\s\S]*/i, "")
      .split("\n")[0]
      .trim();
    const summary = text ? text.slice(0, 180) : "Runner error";
    return { agent, summary };
  }, [triggers]);

  // Derive channel agents list for TopBar (agent_type + running status)
  const channelAgents = useMemo(
    () =>
      mergedAgents.map((a) => ({
        id: a.id,
        agent: a.agent_type,
        running: a.status === "working" || a.status === "idle",
        prompt: a.prompt || "",
        pid: a.pid || null,
        started_at: a.started_at || null,
      })),
    [mergedAgents],
  );

  // Pending approval count for TopBar pill
  const pendingCount = useMemo(
    () => activeMessages.filter((m) => m.type === "tool_approval" && m.status === "pending").length,
    [activeMessages],
  );

  const handleApproveToolRequest = useCallback(async (approvalId) => {
    try {
      await approveToolRequest(approvalId);
    } catch (err) {
      console.error("Failed to approve tool request:", err);
    }
  }, []);

  const handleDenyToolRequest = useCallback(async (approvalId) => {
    try {
      await denyToolRequest(approvalId);
    } catch (err) {
      console.error("Failed to deny tool request:", err);
    }
  }, []);

  const handleReplyToMessage = useCallback((message) => {
    setReplyingTo(message);
  }, []);

  const handleTogglePinMessage = useCallback((message) => {
    if (!message?.id || !activeChannelId) return;
    setPinnedByChannelId((prev) => {
      const existing = prev[activeChannelId] || [];
      const next = existing.includes(message.id)
        ? existing.filter((id) => id !== message.id)
        : [message.id, ...existing];
      return { ...prev, [activeChannelId]: next };
    });
  }, [activeChannelId]);

  const handleDeleteMessage = useCallback(async (message) => {
    if (!message?.id || !activeChannelId) return;
    try {
      await deleteChannelMessage(message.id);
      setMessagesByChannelId((prev) => ({
        ...prev,
        [activeChannelId]: decorateMessages((prev[activeChannelId] || []).filter((item) => item.id !== message.id)),
      }));
      setPinnedByChannelId((prev) => ({
        ...prev,
        [activeChannelId]: (prev[activeChannelId] || []).filter((id) => id !== message.id),
      }));
      if (replyingTo?.id === message.id) {
        setReplyingTo(null);
      }
    } catch (err) {
      console.error("Failed to delete message:", err);
    }
  }, [activeChannelId, replyingTo]);

  const handleConvertMessageToJob = useCallback(async (message) => {
    if (!message || !activeChannelId) return;
    const sourceText = String(message.content || message.text || "").trim();
    if (!sourceText) return;
    const title = sourceText.split("\n")[0].slice(0, 80) || "New job";
    try {
      const created = await createJob({
        title,
        body: sourceText,
        channel: activeChannelId,
        created_by: "human",
      });
      setJobsByChannelId((prev) => ({
        ...prev,
        [activeChannelId]: [normalizeJobs([created])[0], ...(prev[activeChannelId] || [])],
      }));
      setActivePanel("jobs");
    } catch (err) {
      console.error("Failed to create job from message:", err);
    }
  }, [activeChannelId]);

  const handleReplyJump = useCallback((messageId) => {
    if (!messageId) return;
    const target = document.getElementById(`message-${messageId}`);
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);

  const onCreate = async (payload) => {
    const created = await createChannel(payload);
    const normalized = normalizeChannels([created])[0];
    setChannels((prev) => [...prev, normalized]);
    setActiveChannelId(normalized.id);
    setCreateOpen(false);
  };

  const handleAddAgent = useCallback(
    async ({ type }) => {
      if (!activeChannelId || !type) {
        return;
      }
      const resolvedChannelId =
        channels.find((channel) => channel.id === activeChannelId || channel.name === activeChannelId)?.id
        || activeChannelId;
      try {
        await addChannelAgent(resolvedChannelId, type);
        await registerRuntimeAgent(resolvedChannelId, type);
        const refreshed = await getChannelAgents(resolvedChannelId);
        setAgents(normalizeAgents(refreshed, resolvedChannelId));
        setAgentError(null);
      } catch (error) {
        console.error("Failed to add agent:", error);
        setAgentError("Failed to add agent");
        try {
          const refreshed = await getChannelAgents(resolvedChannelId);
          setAgents(normalizeAgents(refreshed, resolvedChannelId));
        } catch { /* keep stale state if refresh also fails */ }
      }
    },
    [activeChannelId, channels],
  );

  const handleToggleAgent = useCallback(
    async (agent) => {
      if (!activeChannelId || !agent?.agent) {
        return;
      }
      const resolvedChannelId =
        channels.find((channel) => channel.id === activeChannelId || channel.name === activeChannelId)?.id
        || activeChannelId;

      try {
        const runtimeResult = agent.running
          ? await deregisterRuntimeAgent(resolvedChannelId, agent.agent)
          : await registerRuntimeAgent(resolvedChannelId, agent.agent);

        if (runtimeResult?.__localFallback) {
          setAgents((prev) =>
            prev.map((item) =>
              item.agent_type === agent.agent
                ? { ...item, status: runtimeResult.status === "idle" ? "idle" : "offline" }
                : item,
            ),
          );
          setAgentError(null);
          return;
        }

        const refreshed = await getChannelAgents(resolvedChannelId);
        setAgents(normalizeAgents(refreshed, resolvedChannelId));
        setAgentError(null);
      } catch (error) {
        console.error("Failed to toggle agent:", error);
        setAgentError("Failed to toggle agent");
      }
    },
    [activeChannelId, channels],
  );

  const handleRemoveAgent = useCallback(
    async (agent) => {
      if (!activeChannelId || !agent?.agent) {
        return;
      }
      const resolvedChannelId =
        channels.find((channel) => channel.id === activeChannelId || channel.name === activeChannelId)?.id
        || activeChannelId;
      try {
        await removeChannelAgent(resolvedChannelId, agent.agent);
        const refreshed = await getChannelAgents(resolvedChannelId);
        setAgents(normalizeAgents(refreshed, resolvedChannelId));
        setAgentError(null);
      } catch (error) {
        console.error("Failed to remove agent:", error);
        setAgentError("Failed to remove agent");
      }
    },
    [activeChannelId, channels],
  );

  const handleOpenRepoChannel = useCallback(
    async (repo) => {
      const repoPath = repo?.path;
      if (!repoPath) return;

      const normalizedRepoPath = normalizeFsPath(repoPath);
      const existing = channels.find(
        (channel) => channel.type === "repo" && normalizeFsPath(channel.repo_path) === normalizedRepoPath,
      );
      if (existing) {
        setActiveChannelId(existing.id);
        return;
      }

      const existingNames = new Set(channels.map((channel) => channel.name));
      const baseName = slugifyName(repo.name || repoPath.split(/[\\/]/).pop() || "repo") || "repo";
      let nextName = baseName;
      let suffix = 2;
      while (existingNames.has(nextName)) {
        nextName = `${baseName}-${suffix}`;
        suffix += 1;
      }

      try {
        const created = await createChannel({
          name: nextName,
          type: "repo",
          repo_path: repoPath,
        });
        const normalized = normalizeChannels([created])[0];
        setChannels((prev) => [...prev, normalized]);
        setActiveChannelId(normalized.id);
      } catch (error) {
        console.error("Failed to open repo channel:", error);
        setChannelError("Failed to open repo channel");
      }
    },
    [channels],
  );

  const onSend = (text) => {
    if (!activeChannelId) {
      return Promise.reject(new Error("No active channel selected"));
    }

    // Optimistic update: show message immediately in the timeline.
    const optimisticId = `optimistic-${Date.now()}`;
    const optimisticMsg = normalizeMessages(
      [{ id: optimisticId, sender: "human", text, channel: activeChannelId, time: Date.now() / 1000, reply_to: replyingTo?.id || null }],
      activeChannelId,
    )[0];
    console.log("[onSend] optimistic message:", optimisticMsg);
    setMessagesByChannelId((prev) => {
      console.log("[onSend] adding optimistic to state, prev count:", (prev[activeChannelId] || []).length);
      return {
        ...prev,
        [activeChannelId]: [...(prev[activeChannelId] || []), optimisticMsg],
      };
    });

    return sendChannelMessage({
      channelId: activeChannelId,
      text,
      sender: "human",
      replyTo: replyingTo?.id || null,
    })
      .then(async () => {
        setReplyingTo(null);
        const targets = extractMentionTargets(
          text,
          mergedAgents.map((agent) => agent.agent_type),
        );
        if (targets.length === 0) {
          return;
        }
        const triggerResults = await Promise.allSettled(
          targets.map((agentType) => triggerAgent(agentType, "user", text, activeChannelId)),
        );
        const anyFailed = triggerResults.some((r) => r.status === "rejected");
        if (anyFailed) {
          setMessagesError("One or more agents are not running");
        }
      })
      .catch((error) => {
        console.error("Failed to send message:", error);
        setMessagesError("Failed to send message");
        throw error;
      });
  };

  const showChannel = activeChannel || channels.find((channel) => channel.id === activeChannelId) || null;
  const reposWithActive = useMemo(
    () =>
      repos.map((repo) => ({
        ...repo,
        active:
          showChannel?.type === "repo"
          && normalizeFsPath(showChannel.repo_path) === normalizeFsPath(repo.path),
      })),
    [repos, showChannel],
  );

  const togglePanel = (name) => {
    setActivePanel((prev) => (prev === name ? null : name));
  };

  const renderPanel = () => {
    switch (activePanel) {
      case "activity":
        return (
          <ActivityPanel
            open
            onClose={() => setActivePanel(null)}
            agentActivity={{}}
          />
        );
      case "agents":
        return (
          <AgentsPanel
            open
            onClose={() => setActivePanel(null)}
            channelName={showChannel?.name}
            agents={channelAgents}
            repos={repos}
            onAddAgent={handleAddAgent}
            onToggleAgent={handleToggleAgent}
            onRemoveAgent={handleRemoveAgent}
          />
        );
      case "jobs":
        return <JobsPanel open onClose={() => setActivePanel(null)} jobs={activeJobs} />;
      case "rules":
        return <RulesPanel open onClose={() => setActivePanel(null)} />;
      case "settings":
        return <SettingsPanel open onClose={() => setActivePanel(null)} />;
      default:
        return null;
    }
  };

  return (
    <>
      <AppShell
        sidebar={
          <Sidebar
            channels={channels}
            repos={reposWithActive}
            pinnedMessages={pinnedMessages}
            activeChannel={activeChannelId}
            onSelectChannel={setActiveChannelId}
            onCreateChannel={() => setCreateOpen(true)}
            onSessionLaunch={() => setSessionLauncherOpen(true)}
            onAddRepo={handleAddRepo}
            onRemoveRepo={handleRemoveRepo}
            onRefreshRepos={fetchRepos}
            onBrowseRepo={handleBrowseRepo}
            onOpenRepoChannel={handleOpenRepoChannel}
          />
        }
        panel={renderPanel()}
      >
        <TopBar
          channelName={showChannel?.name || ""}
          channelAgents={channelAgents}
          pendingCount={pendingCount}
          activePanel={activePanel}
          onTogglePanel={togglePanel}
        />

        {channelError && (
          <div style={{ padding: "4px 16px", color: "var(--warning)", fontSize: "var(--fs-label, 11px)" }}>
            {channelError}
          </div>
        )}
        {messagesError && (
          <div style={{ padding: "4px 16px", color: "var(--warning)", fontSize: "var(--fs-label, 11px)" }}>
            Message sync issue: {messagesError}
          </div>
        )}

        <ChatTimeline
          messages={activeMessages}
          channelName={showChannel?.name}
          onApprove={handleApproveToolRequest}
          onDeny={handleDenyToolRequest}
          onReply={handleReplyToMessage}
          onDelete={handleDeleteMessage}
          onPin={handleTogglePinMessage}
          onConvertToJob={handleConvertMessageToJob}
          onReplyJump={handleReplyJump}
          pinnedMessageIds={activeChannelId ? pinnedByChannelId[activeChannelId] || [] : []}
        />

        <AgentThinkingStrip
          agents={mergedAgents}
          failure={latestAgentFailure}
        />

        <Composer
          onSendMessage={onSend}
          onSchedule={() => setScheduleModalOpen(true)}
          replyMessage={replyingTo}
          onCancelReply={() => setReplyingTo(null)}
        />
      </AppShell>

      <CreateChannelModal open={createOpen} onClose={() => setCreateOpen(false)} onCreate={onCreate} repos={repos} />
      <SessionLauncher open={sessionLauncherOpen} onClose={() => setSessionLauncherOpen(false)} />
      <ScheduleModal open={scheduleModalOpen} onClose={() => setScheduleModalOpen(false)} />
    </>
  );
}
