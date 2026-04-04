"""ClaudeBridge — controls a Claude Code agent via HTTP hooks + keystroke injection.

Claude Code does not have a programmatic prompt API like Codex's app-server,
so this bridge uses:

- **HTTP hooks** (settings.local.json) for observing and gating tool calls
- **Keystroke injection** (existing injector module) for sending prompts
- **Process management** for lifecycle control
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import sys
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
    ErrorEvent,
    StatusChangeEvent,
    SubagentEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from duckdome.wrapper.injector import inject

logger = logging.getLogger(__name__)

_JsonDict = dict[str, Any]
PreToolUseHandler = Callable[[str, dict[str, object], str], _JsonDict]


class ClaudeBridge(AgentBridge):
    """Bridge to a Claude Code agent via HTTP hooks and keystroke injection."""

    def __init__(self, receiver_port: int) -> None:
        super().__init__()
        self._receiver_port = receiver_port
        self._agent_id: str = ""
        self._config: AgentConfig | None = None
        self._proc: subprocess.Popen[str] | None = None
        self._status = AgentStatus.OFFLINE
        self._settings_dir: Path | None = None
        # approval_id → asyncio.Event + decision dict
        self._pending_approvals: dict[str, tuple[threading.Event, _JsonDict]] = {}
        # Set when the CLI is ready to accept input (SessionStart hook fires)
        self._ready = threading.Event()
        self._pre_tool_use_handler: PreToolUseHandler | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, agent_id: str, config: AgentConfig) -> None:
        self._ready.clear()
        self._agent_id = agent_id
        self._config = config

        claude_bin = shutil.which("claude")
        if claude_bin is None:
            raise FileNotFoundError("claude binary not found on PATH")

        # Generate hook settings pointing at our receiver
        settings_path = generate_claude_hook_settings(
            agent_id=agent_id,
            receiver_port=self._receiver_port,
        )
        self._settings_dir = settings_path.parent

        # Register ourselves as the handler for this agent's hooks
        register_hook_handler(agent_id, self._handle_hook)

        # Build launch command (match legacy launcher in providers.py)
        mcp_config_path = config.extra.get("mcp_config_path", "")
        cmd = [claude_bin]
        if mcp_config_path:
            cmd.extend([
                "--mcp-config", str(mcp_config_path),
                "--strict-mcp-config",
            ])
            # Allow DuckDome MCP tools explicitly
            for tool_name in ("chat_join", "chat_read", "chat_rules", "chat_send"):
                cmd.extend(["--allowedTools", f"mcp__duckdome__{tool_name}"])

        env = os.environ.copy()
        env.update(config.extra.get("env", {}))
        # Point Claude at our hook settings directory
        env["CLAUDE_LOCAL_SETTINGS_DIR"] = str(self._settings_dir)

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NEW_CONSOLE

        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=config.cwd,
            env=env,
            creationflags=creationflags,
        )

        logger.info(
            "Claude agent %s started pid=%d with hooks at %s",
            agent_id, self._proc.pid, settings_path,
        )

        self._status = AgentStatus.IDLE
        self._emit(self.STATUS_CHANGE, StatusChangeEvent(
            agent_id=agent_id,
            agent_type="claude",
            channel_id=config.channel_id,
            status=AgentStatus.IDLE,
        ))

    async def stop(self) -> None:
        self._ready.clear()
        unregister_hook_handler(self._agent_id)

        # Fail pending approvals
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
        if not self._proc or self._proc.poll() is not None:
            raise RuntimeError("Claude process not running")

        # Wait for the CLI to be ready (SessionStart hook fires)
        ready = await asyncio.to_thread(self._ready.wait, 30)
        if not ready:
            raise TimeoutError(
                f"Claude agent {self._agent_id} did not become ready within 30s"
            )

        # Re-check process after the wait — stop() may have fired
        proc = self._proc
        if not proc or proc.poll() is not None:
            raise RuntimeError("Claude process stopped before prompt injection")

        self._status = AgentStatus.WORKING
        self._emit(self.STATUS_CHANGE, StatusChangeEvent(
            agent_id=self._agent_id,
            agent_type="claude",
            channel_id=channel_id,
            status=AgentStatus.WORKING,
        ))

        pid = proc.pid
        tmux_session = self._config.extra.get("tmux_session") if self._config else None

        success = await asyncio.to_thread(
            inject, text, pid, 0.05, tmux_session=tmux_session,
        )
        if not success:
            logger.error("Failed to inject prompt into Claude agent %s", self._agent_id)

    async def interrupt(self) -> None:
        if not self._proc or self._proc.poll() is not None:
            return
        # Send Escape key to interrupt Claude
        pid = self._proc.pid
        tmux_session = self._config.extra.get("tmux_session") if self._config else None
        await asyncio.to_thread(
            inject, "\x1b", pid, 0.01, tmux_session=tmux_session,
        )

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
                if not self._ready.is_set():
                    logger.info("Claude agent %s ready (SessionStart received)", self._agent_id)
                    self._ready.set()
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
