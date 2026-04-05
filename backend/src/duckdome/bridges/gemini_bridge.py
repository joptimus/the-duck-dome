"""GeminiBridge — controls a Google Gemini agent via ACP stdio JSON-RPC.

Spawns ``gemini --acp`` and communicates over stdin/stdout using the
Agent Client Protocol (JSON-RPC 2.0).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from duckdome.bridges.base import AgentBridge, AgentConfig
from duckdome.bridges.events import (
    AgentMessageDeltaEvent,
    AgentMessageEvent,
    AgentStatus,
    ApprovalRequestEvent,
    ErrorEvent,
    StatusChangeEvent,
    ToolCallEvent,
    ToolResultEvent,
)

logger = logging.getLogger(__name__)

_JsonDict = dict[str, Any]


def _make_request(method: str, params: _JsonDict, request_id: str | None = None) -> _JsonDict:
    return {
        "jsonrpc": "2.0",
        "id": request_id or str(uuid.uuid4()),
        "method": method,
        "params": params,
    }


def _make_notification(method: str, params: _JsonDict | None = None) -> _JsonDict:
    msg: _JsonDict = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def _make_response(request_id: str, result: _JsonDict) -> _JsonDict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _make_error_response(request_id: str, code: int, message: str) -> _JsonDict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


class GeminiBridge(AgentBridge):
    """Bridge to a Gemini CLI agent via the ACP stdio protocol."""

    def __init__(self) -> None:
        super().__init__()
        self._agent_id: str = ""
        self._config: AgentConfig | None = None
        self._proc: subprocess.Popen[str] | None = None
        self._read_task: asyncio.Task[None] | None = None
        self._status = AgentStatus.OFFLINE
        self._session_id: str | None = None
        self._pending_requests: dict[str, asyncio.Future[_JsonDict]] = {}
        self._pending_approvals: dict[str, asyncio.Future[_JsonDict]] = {}
        self._write_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle (filled in by later tasks)
    # ------------------------------------------------------------------

    async def start(self, agent_id: str, config: AgentConfig) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Communication (filled in by later tasks)
    # ------------------------------------------------------------------

    async def send_prompt(self, text: str, channel_id: str, sender: str) -> None:
        raise NotImplementedError

    async def interrupt(self) -> None:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Approval (filled in by later tasks)
    # ------------------------------------------------------------------

    async def approve(self, approval_id: str) -> None:
        raise NotImplementedError

    async def deny(self, approval_id: str, reason: str) -> None:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def get_status(self) -> AgentStatus:
        return self._status
