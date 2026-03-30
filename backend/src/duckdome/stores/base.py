from __future__ import annotations

from abc import ABC, abstractmethod

from duckdome.models.channel import AgentInstance, Channel


class BaseChannelStore(ABC):
    @abstractmethod
    def add_channel(self, channel: Channel) -> Channel: ...

    @abstractmethod
    def get_channel(self, channel_id: str) -> Channel | None: ...

    @abstractmethod
    def list_channels(self) -> list[Channel]: ...

    @abstractmethod
    def add_agent(self, agent: AgentInstance) -> AgentInstance: ...

    @abstractmethod
    def get_agent(self, agent_id: str) -> AgentInstance | None: ...

    @abstractmethod
    def list_agents(self, channel_id: str) -> list[AgentInstance]: ...

    @abstractmethod
    def update_agent(self, agent_id: str, agent: AgentInstance) -> AgentInstance | None: ...

    @abstractmethod
    def remove_agent(self, agent_id: str) -> bool: ...
