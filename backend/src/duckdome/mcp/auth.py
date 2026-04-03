from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True)
class BoundAgentIdentity:
    channel: str
    agent_type: str


_REQUEST_TOKEN: ContextVar[str | None] = ContextVar("duckdome_mcp_request_token", default=None)


class AgentAuthStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._tokens: dict[str, BoundAgentIdentity] = {}

    def register(self, token: str, *, channel: str, agent_type: str) -> None:
        with self._lock:
            self._tokens[token] = BoundAgentIdentity(channel=channel, agent_type=agent_type)

    def unregister(self, token: str) -> None:
        with self._lock:
            self._tokens.pop(token, None)

    def get(self, token: str | None) -> BoundAgentIdentity | None:
        if not token:
            return None
        with self._lock:
            return self._tokens.get(token)


agent_auth_store = AgentAuthStore()


def set_request_token(token: str | None):
    return _REQUEST_TOKEN.set(token)


def reset_request_token(token_state) -> None:
    _REQUEST_TOKEN.reset(token_state)


def get_request_token() -> str | None:
    return _REQUEST_TOKEN.get()

