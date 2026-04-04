"""ClaudeBridge — controls a Claude Code agent via --print mode + HTTP hooks.

Each send_prompt() spawns a fresh `claude --print <text>` process.
HTTP hooks (settings.local.json) observe tool calls and gate permissions.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Any, Callable

from duckdome.bridges.base import AgentBridge, AgentConfig
from duckdome.bridges.claude_hook_receiver import (
    register_hook_handler,
    unregister_hook_handler,
)
from duckdome.bridges.claude_settings import generate_claude_hook_settings
from duckdome.bridges.events import (
    AgentMessageEvent,
    AgentStatus,
    ApprovalRequestEvent,
    StatusChangeEvent,
    SubagentEvent,
    ToolCallEvent,
    ToolResultEvent,
)

logger = logging.getLogger(__name__)

_JsonDict = dict[str, Any]
PreToolUseHandler = Callable[[str, dict[str, object], str], _JsonDict]


class ClaudeBridge(AgentBridge):
    """Bridge to a Claude Code agent using --print mode.

    Each send_prompt() spawns a fresh `claude --print <text>` process.
    No persistent session or keystroke injection needed — Claude uses
    the DuckDome MCP tools (chat_read, chat_send) to communicate.
    The channel/identity context is injected via --append-system-prompt.
    """

    def __init__(self, receiver_port: int) -> None:
        super().__init__()
        self._receiver_port = receiver_port
        self._agent_id: str = ""
        self._config: AgentConfig | None = None
        self._proc: subprocess.Popen[str] | None = None
        self._status = AgentStatus.OFFLINE
        self._settings_path: Path | None = None
        self._pending_approvals: dict[str, tuple[threading.Event, _JsonDict]] = {}
        self._pre_tool_use_handler: PreToolUseHandler | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, agent_id: str, config: AgentConfig) -> None:
        """Store config and generate hook settings. No persistent process."""
        self._agent_id = agent_id
        self._config = config

        claude_bin = shutil.which("claude")
        if claude_bin is None:
            raise FileNotFoundError("claude binary not found on PATH")

        # Generate hook settings for tool call observation
        settings_path = generate_claude_hook_settings(
            agent_id=agent_id,
            receiver_port=self._receiver_port,
        )
        self._settings_path = settings_path

        # Register hook handler for tool call events
        register_hook_handler(agent_id, self._handle_hook)

        logger.info("Claude bridge %s ready (--print mode), hooks at %s", agent_id, settings_path)

        self._status = AgentStatus.IDLE
        self._emit(self.STATUS_CHANGE, StatusChangeEvent(
            agent_id=agent_id,
            agent_type="claude",
            channel_id=config.channel_id,
            status=AgentStatus.IDLE,
        ))

    async def stop(self) -> None:
        unregister_hook_handler(self._agent_id)

        for approval_id, (event, decision) in self._pending_approvals.items():
            decision["decision"] = "block"
            decision["reason"] = "Bridge stopping"
            event.set()
        self._pending_approvals.clear()

        if self._proc:
            proc = self._proc
            self._proc = None
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                proc.kill()

        self._status = AgentStatus.OFFLINE
        if self._config:
            self._emit(self.STATUS_CHANGE, StatusChangeEvent(
                agent_id=self._agent_id,
                agent_type="claude",
                channel_id=self._config.channel_id,
                status=AgentStatus.OFFLINE,
            ))

    # ------------------------------------------------------------------
    # Communication
    # ------------------------------------------------------------------

    async def send_prompt(self, text: str, channel_id: str, sender: str) -> None:
        """Spawn `claude --print <text>` and wait for it to complete."""
        if self._config is None:
            raise RuntimeError("ClaudeBridge not started")

        claude_bin = shutil.which("claude")
        if claude_bin is None:
            raise FileNotFoundError("claude binary not found on PATH")

        cmd = [claude_bin, "--print", text]

        if self._settings_path:
            cmd.extend(["--settings", str(self._settings_path)])

        mcp_config_path = self._config.extra.get("mcp_config_path", "")
        if mcp_config_path and Path(mcp_config_path).exists():
            cmd.extend(["--mcp-config", mcp_config_path])

        self._status = AgentStatus.WORKING
        self._emit(self.STATUS_CHANGE, StatusChangeEvent(
            agent_id=self._agent_id,
            agent_type="claude",
            channel_id=channel_id,
            status=AgentStatus.WORKING,
        ))

        logger.info("[%s] spawning claude --print for channel=%s", self._agent_id, channel_id)

        def _run() -> int:
            proc = subprocess.Popen(
                cmd,
                cwd=self._config.cwd if self._config else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self._proc = proc
            stdout, stderr = proc.communicate()
            self._proc = None
            if stdout:
                logger.debug("[%s] claude stdout: %s", self._agent_id, stdout[:500])
            if stderr:
                logger.debug("[%s] claude stderr: %s", self._agent_id, stderr[:500])
            return proc.returncode

        returncode = await asyncio.to_thread(_run)

        if returncode != 0:
            logger.warning("[%s] claude --print exited with code %d", self._agent_id, returncode)

    async def interrupt(self) -> None:
        proc = self._proc
        if proc and proc.poll() is None:
            proc.terminate()

    # ------------------------------------------------------------------
    # Approval
    # ------------------------------------------------------------------

    async def approve(self, approval_id: str) -> None:
        entry = self._pending_approvals.get(approval_id)
        if entry:
            event, decision = entry
            decision["decision"] = "approve"
            event.set()

    async def deny(self, approval_id: str, reason: str) -> None:
        entry = self._pending_approvals.get(approval_id)
        if entry:
            event, decision = entry
            decision["decision"] = "block"
            decision["reason"] = reason
            event.set()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def get_status(self) -> AgentStatus:
        if self._proc and self._proc.poll() is not None:
            self._status = AgentStatus.OFFLINE
        return self._status

    def set_pre_tool_use_handler(
        self,
        handler: PreToolUseHandler | None,
    ) -> None:
        self._pre_tool_use_handler = handler

    # ------------------------------------------------------------------
    # Hook handler (called synchronously from FastAPI endpoint)
    # ------------------------------------------------------------------

    def _handle_hook(self, hook_event: str, payload: _JsonDict) -> _JsonDict:
        """Process an incoming Claude Code hook event.

        Called from the HTTP hook receiver on the FastAPI request thread.
        Must return a dict that becomes the hook JSON response.
        """
        channel_id = self._config.channel_id if self._config else ""

        match hook_event:
            case "PreToolUse":
                return self._handle_pre_tool_use(payload, channel_id)
            case "PostToolUse":
                self._handle_post_tool_use(payload, channel_id)
            case "PostToolUseFailure":
                self._handle_post_tool_use_failure(payload, channel_id)
            case "PermissionRequest":
                return self._handle_permission_request(payload, channel_id)
            case "SubagentStart":
                self._emit(self.SUBAGENT, SubagentEvent(
                    agent_id=self._agent_id,
                    agent_type="claude",
                    channel_id=channel_id,
                    subagent_id=payload.get("agent_id", ""),
                    subagent_type=payload.get("agent_type", ""),
                    started=True,
                ))
            case "SubagentStop":
                self._emit(self.SUBAGENT, SubagentEvent(
                    agent_id=self._agent_id,
                    agent_type="claude",
                    channel_id=channel_id,
                    subagent_id=payload.get("agent_id", ""),
                    subagent_type=payload.get("agent_type", ""),
                    started=False,
                    last_message=payload.get("last_assistant_message"),
                ))
            case "Stop":
                self._status = AgentStatus.IDLE
                self._emit(self.STATUS_CHANGE, StatusChangeEvent(
                    agent_id=self._agent_id,
                    agent_type="claude",
                    channel_id=channel_id,
                    status=AgentStatus.IDLE,
                ))
                last_msg = payload.get("last_assistant_message")
                if last_msg:
                    self._emit(self.MESSAGE, AgentMessageEvent(
                        agent_id=self._agent_id,
                        agent_type="claude",
                        channel_id=channel_id,
                        text=last_msg,
                    ))
            case "SessionStart":
                logger.info("Claude agent %s SessionStart received", self._agent_id)
            case "Notification":
                logger.info(
                    "Claude notification [%s]: %s",
                    payload.get("notification_type", ""),
                    payload.get("message", ""),
                )
            case _:
                logger.debug("Unhandled Claude hook: %s", hook_event)

        return {}

    def _handle_pre_tool_use(self, payload: _JsonDict, channel_id: str) -> _JsonDict:
        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input", {})
        call_id = payload.get("tool_use_id", "")
        normalized_input = tool_input if isinstance(tool_input, dict) else {}

        self._emit(self.TOOL_CALL, ToolCallEvent(
            agent_id=self._agent_id,
            agent_type="claude",
            channel_id=channel_id,
            tool_name=tool_name,
            tool_input=normalized_input,
            call_id=call_id,
        ))

        if self._pre_tool_use_handler is not None:
            return self._pre_tool_use_handler(tool_name, normalized_input, channel_id)

        return {}

    def _handle_post_tool_use(self, payload: _JsonDict, channel_id: str) -> None:
        tool_name = payload.get("tool_name", "")
        call_id = payload.get("tool_use_id", "")
        tool_response = payload.get("tool_response", "")

        self._emit(self.TOOL_RESULT, ToolResultEvent(
            agent_id=self._agent_id,
            agent_type="claude",
            channel_id=channel_id,
            tool_name=tool_name,
            call_id=call_id,
            success=True,
            output=str(tool_response)[:2000],
        ))

    def _handle_post_tool_use_failure(self, payload: _JsonDict, channel_id: str) -> None:
        tool_name = payload.get("tool_name", "")
        call_id = payload.get("tool_use_id", "")
        error = payload.get("error", "")

        self._emit(self.TOOL_RESULT, ToolResultEvent(
            agent_id=self._agent_id,
            agent_type="claude",
            channel_id=channel_id,
            tool_name=tool_name,
            call_id=call_id,
            success=False,
            output=str(error)[:2000],
        ))

    def _handle_permission_request(self, payload: _JsonDict, channel_id: str) -> _JsonDict:
        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input", {})
        approval_id = str(uuid.uuid4())

        # Create a threading.Event so the hook handler can block until
        # the user responds via approve()/deny().
        event = threading.Event()
        decision: _JsonDict = {}
        self._pending_approvals[approval_id] = (event, decision)

        self._emit(self.APPROVAL_REQUEST, ApprovalRequestEvent(
            agent_id=self._agent_id,
            agent_type="claude",
            channel_id=channel_id,
            approval_id=approval_id,
            tool_name=tool_name,
            tool_input=tool_input if isinstance(tool_input, dict) else {},
            description=f"{tool_name} permission request",
        ))

        # Block until approve/deny is called or timeout (10 min matches CLI default)
        event.wait(timeout=600)
        self._pending_approvals.pop(approval_id, None)

        if decision.get("decision") == "approve":
            return {"decision": "approve"}
        elif decision.get("decision") == "block":
            return {"decision": "block", "reason": decision.get("reason", "Denied by user")}

        # Timeout — decline
        return {"decision": "block", "reason": "Approval timed out"}
