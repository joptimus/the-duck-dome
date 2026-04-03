"""Unified agent bridge abstractions.

Provides a common interface for controlling CLI agents (Claude Code, Codex,
etc.) so the rest of DuckDome doesn't need to know which backend is in use.
"""
from duckdome.bridges.base import AgentBridge, AgentConfig
from duckdome.bridges.codex_bridge import CodexBridge
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

__all__ = [
    "AgentBridge",
    "AgentConfig",
    "AgentMessageDeltaEvent",
    "AgentMessageEvent",
    "AgentStatus",
    "ApprovalRequestEvent",
    "CodexBridge",
    "ErrorEvent",
    "StatusChangeEvent",
    "SubagentEvent",
    "ToolCallEvent",
    "ToolResultEvent",
]
