from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator, TypeVar

from pydantic import BaseModel, ValidationError

from duckdome.models.channel import AgentInstance, Channel

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)


def iter_jsonl_models(path: Path, model_cls: type[ModelT]) -> Iterator[ModelT]:
    """Yield models from a JSONL file, skipping corrupt lines.

    A torn line (crash mid-append) or schema mismatch must not prevent the
    store — and therefore the whole backend — from loading.
    """
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield model_cls(**json.loads(line))
            except (json.JSONDecodeError, ValidationError, TypeError) as exc:
                logger.warning(
                    "Skipping corrupt line %d in %s: %s", lineno, path.name, exc
                )


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

    @abstractmethod
    def delete_channel(self, channel_id: str) -> bool: ...
