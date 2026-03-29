from __future__ import annotations

import json
import os
from pathlib import Path

from duckdome.models.channel import AgentInstance, Channel
from duckdome.stores.base import BaseChannelStore


class ChannelStore(BaseChannelStore):
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._channels_file = self._data_dir / "channels.jsonl"
        self._agents_file = self._data_dir / "agents.jsonl"
        self._channels: dict[str, Channel] = {}
        self._channel_order: list[str] = []
        self._agents: dict[str, AgentInstance] = {}
        self._load()

    def _load(self) -> None:
        if self._channels_file.exists():
            with open(self._channels_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    ch = Channel(**json.loads(line))
                    self._channels[ch.id] = ch
                    if ch.id not in self._channel_order:
                        self._channel_order.append(ch.id)
        if self._agents_file.exists():
            with open(self._agents_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    agent = AgentInstance(**json.loads(line))
                    self._agents[agent.id] = agent

    def _save_channels(self) -> None:
        tmp = self._channels_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for cid in self._channel_order:
                f.write(self._channels[cid].model_dump_json() + "\n")
            f.flush()
            os.fsync(f.fileno())
        tmp.rename(self._channels_file)

    def _save_agents(self) -> None:
        tmp = self._agents_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for agent in self._agents.values():
                f.write(agent.model_dump_json() + "\n")
            f.flush()
            os.fsync(f.fileno())
        tmp.rename(self._agents_file)

    def add_channel(self, channel: Channel) -> Channel:
        if channel.id in self._channels:
            return self._channels[channel.id]
        self._channels[channel.id] = channel
        self._channel_order.append(channel.id)
        self._save_channels()
        return channel

    def get_channel(self, channel_id: str) -> Channel | None:
        return self._channels.get(channel_id)

    def list_channels(self) -> list[Channel]:
        return [self._channels[cid] for cid in self._channel_order]

    def add_agent(self, agent: AgentInstance) -> AgentInstance:
        if agent.id in self._agents:
            return self._agents[agent.id]
        self._agents[agent.id] = agent
        self._save_agents()
        return agent

    def get_agent(self, agent_id: str) -> AgentInstance | None:
        return self._agents.get(agent_id)

    def list_agents(self, channel_id: str) -> list[AgentInstance]:
        return [a for a in self._agents.values() if a.channel_id == channel_id]

    def update_agent(self, agent_id: str, agent: AgentInstance) -> AgentInstance | None:
        if agent_id not in self._agents:
            return None
        self._agents[agent_id] = agent
        self._save_agents()
        return agent
