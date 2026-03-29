import { useEffect, useMemo, useState } from "react";
import { createChannel, getChannel, getChannelAgents, getChannels } from "./api";
import { mockMessagesByChannelId } from "./mockData";
import AgentStatusRow from "./components/AgentStatusRow";
import ChannelCreateModal from "./components/ChannelCreateModal";
import ChannelHeader from "./components/ChannelHeader";
import ChatShell from "./components/ChatShell";
import SidebarChannelList from "./components/SidebarChannelList";
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

export default function ChannelShell() {
  const [channels, setChannels] = useState([]);
  const [activeChannelId, setActiveChannelId] = useState(null);
  const [activeChannel, setActiveChannel] = useState(null);
  const [agents, setAgents] = useState([]);
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
      const [channel, channelAgents] = await Promise.all([
        getChannel(activeChannelId),
        getChannelAgents(activeChannelId),
      ]);
      if (ignore) return;
      setActiveChannel(channel);
      setAgents(Array.isArray(channelAgents) ? channelAgents : []);
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
        <ChannelHeader channel={activeChannel} />
        <AgentStatusRow agents={agents} />
        <ChatShell channel={activeChannel} messages={activeMessages} onSend={onSend} />
      </main>

      <ChannelCreateModal open={createOpen} onClose={() => setCreateOpen(false)} onCreate={onCreate} />
    </div>
  );
}
