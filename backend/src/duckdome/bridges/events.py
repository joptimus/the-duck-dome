"""Unified event model for agent bridges.

Both ClaudeBridge and CodexBridge emit these normalized events into the
DuckDome event bus so the rest of the system (channels, chat, UI, task
routing) doesn't care which CLI backend an agent runs on.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum


class AgentStatus(StrEnum):
    IDLE = "idle"
    WORKING = "working"
    OFFLINE = "offline"


# ---------------------------------------------------------------------------
# Events emitted by bridges
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ToolCallEvent:
    """A tool/command is about to be executed."""
    agent_id: str
    agent_type: str
    channel_id: str
    tool_name: str
    tool_input: dict
    call_id: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ToolResultEvent:
    """A tool/command finished executing."""
    agent_id: str
    agent_type: str
    channel_id: str
    tool_name: str
    call_id: str
    success: bool
    output: str
    duration_ms: float | None = None
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class AgentMessageEvent:
    """Complete agent text output (final message)."""
    agent_id: str
    agent_type: str
    channel_id: str
    text: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class AgentMessageDeltaEvent:
    """Streaming text chunk from agent."""
    agent_id: str
    agent_type: str
    channel_id: str
    delta: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ApprovalRequestEvent:
    """Agent is requesting approval for a tool/command execution."""
    agent_id: str
    agent_type: str
    channel_id: str
    approval_id: str
    tool_name: str
    tool_input: dict
    description: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class StatusChangeEvent:
    """Agent status changed (idle / working / offline)."""
    agent_id: str
    agent_type: str
    channel_id: str
    status: AgentStatus
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class SubagentEvent:
    """A subagent started or stopped."""
    agent_id: str
    agent_type: str
    channel_id: str
    subagent_id: str
    subagent_type: str
    started: bool
    last_message: str | None = None
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ErrorEvent:
    """An error occurred in the agent."""
    agent_id: str
    agent_type: str
    channel_id: str
    error: str
    details: str | None = None
    timestamp: float = field(default_factory=time.time)
