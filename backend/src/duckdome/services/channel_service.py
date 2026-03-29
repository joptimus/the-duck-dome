from __future__ import annotations

from pathlib import Path

from duckdome.models.channel import AgentInstance, Channel, ChannelType
from duckdome.stores.base import BaseChannelStore


class ChannelService:
    def __init__(self, store: BaseChannelStore) -> None:
        self._store = store

    def create_channel(
        self,
        name: str,
        type: str,
        repo_path: str | None = None,
    ) -> Channel:
        channel_type = ChannelType(type)
        if channel_type == ChannelType.REPO:
            if not repo_path:
                raise ValueError("repo_path is required for repo channels")
            if not Path(repo_path).is_dir():
                raise ValueError(f"repo_path does not exist: {repo_path}")
        channel = Channel(name=name, type=channel_type, repo_path=repo_path)
        return self._store.add_channel(channel)

    def get_channel(self, channel_id: str) -> Channel | None:
        return self._store.get_channel(channel_id)

    def list_channels(self) -> list[Channel]:
        return self._store.list_channels()

    def validate_channel(self, channel_id: str) -> bool:
        return self._store.get_channel(channel_id) is not None

    def add_agent(self, channel_id: str, agent_type: str) -> AgentInstance:
        if not self.validate_channel(channel_id):
            raise ValueError(f"Channel not found: {channel_id}")
        agent = AgentInstance(channel_id=channel_id, agent_type=agent_type)
        return self._store.add_agent(agent)

    def list_agents(self, channel_id: str) -> list[AgentInstance]:
        return self._store.list_agents(channel_id)

    def get_agent_types(self, channel_id: str) -> list[str]:
        agents = self._store.list_agents(channel_id)
        return [a.agent_type for a in agents]
