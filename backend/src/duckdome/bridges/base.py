"""Abstract base class for agent bridges.

An AgentBridge abstracts the communication with a CLI agent process
(Claude Code, Codex, etc.) behind a single interface.  The rest of
DuckDome talks to agents *only* through this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable

from duckdome.bridges.events import (
    AgentMessageDeltaEvent,
    AgentMessageEvent,
    AgentStatus,
    ApprovalRequestEvent,
    ErrorEvent,
    StatusChangeEvent,
    SubagentEvent,
    ToolCallEvent,
    ToolResultEvent,
)


@dataclass
class AgentConfig:
    """Configuration passed to a bridge at startup."""
    agent_type: str
    channel_id: str
    cwd: str
    mcp_url: str = ""
    extra: dict = field(default_factory=dict)


# Callbacks MUST be synchronous — async callables will silently fail.
# This matches the existing DuckDome broadcast pattern (broadcast_sync).
EventCallback = Callable[..., None]


class AgentBridge(ABC):
    """Unified interface for controlling an agent regardless of CLI backend."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[EventCallback]] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    async def start(self, agent_id: str, config: AgentConfig) -> None:
        """Spawn the agent process and establish connection."""

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully stop the agent."""

    # ------------------------------------------------------------------
    # Communication
    # ------------------------------------------------------------------

    @abstractmethod
    async def send_prompt(self, text: str, channel_id: str, sender: str) -> None:
        """Send a message/task to the agent."""

    @abstractmethod
    async def interrupt(self) -> None:
        """Interrupt the agent's current turn."""

    # ------------------------------------------------------------------
    # Approval
    # ------------------------------------------------------------------

    @abstractmethod
    async def approve(self, approval_id: str) -> None:
        """Approve a pending tool/command execution."""

    @abstractmethod
    async def deny(self, approval_id: str, reason: str) -> None:
        """Deny a pending tool/command execution."""

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_status(self) -> AgentStatus:
        ...

    # ------------------------------------------------------------------
    # Event system  (bridges call _emit; consumers call on())
    # ------------------------------------------------------------------

    def on(self, event_type: str, callback: EventCallback) -> None:
        """Register a callback for a bridge event type."""
        self._listeners.setdefault(event_type, []).append(callback)

    def _emit(self, event_type: str, event: object) -> None:
        """Emit an event to all registered listeners.

        Each listener is called inside a try/except so a failing callback
        cannot crash the bridge's read loop or other transports.
        """
        for cb in self._listeners.get(event_type, []):
            try:
                cb(event)
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "Bridge event listener failed: event_type=%s listener=%r",
                    event_type, cb,
                )

    # Convenience constants for event types
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    MESSAGE = "message"
    MESSAGE_DELTA = "message_delta"
    APPROVAL_REQUEST = "approval_request"
    STATUS_CHANGE = "status_change"
    SUBAGENT = "subagent"
    ERROR = "error"
