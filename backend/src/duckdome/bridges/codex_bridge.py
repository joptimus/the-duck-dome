"""CodexBridge — controls an OpenAI Codex agent via app-server JSON-RPC.

Spawns ``codex app-server --listen stdio://`` and communicates over
stdin/stdout using the v2 JSON-RPC protocol.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import uuid
from typing import Any

from duckdome.bridges.base import AgentBridge, AgentConfig
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

logger = logging.getLogger(__name__)

# JSON-RPC helpers --------------------------------------------------------

_JsonDict = dict[str, Any]


def _make_request(method: str, params: _JsonDict, request_id: str | None = None) -> _JsonDict:
    return {
        "jsonrpc": "2.0",
        "id": request_id or str(uuid.uuid4()),
        "method": method,
        "params": params,
    }


def _make_response(request_id: str, result: _JsonDict) -> _JsonDict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }


def _make_notification(method: str, params: _JsonDict | None = None) -> _JsonDict:
    msg: _JsonDict = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    return msg


class CodexBridge(AgentBridge):
    """Bridge to an OpenAI Codex agent via the app-server stdio protocol."""

    def __init__(self) -> None:
        super().__init__()
        self._agent_id: str = ""
        self._config: AgentConfig | None = None
        self._proc: subprocess.Popen[str] | None = None
        self._read_task: asyncio.Task[None] | None = None
        self._status = AgentStatus.OFFLINE
        self._thread_id: str | None = None
        self._active_turn_id: str | None = None
        self._pending_requests: dict[str, asyncio.Future[_JsonDict]] = {}
        self._pending_approvals: dict[str, asyncio.Future[_JsonDict]] = {}
        self._write_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, agent_id: str, config: AgentConfig) -> None:
        self._agent_id = agent_id
        self._config = config

        codex_bin = shutil.which("codex")
        if codex_bin is None:
            raise FileNotFoundError("codex binary not found on PATH")

        args = [codex_bin, "app-server", "--listen", "stdio://"]

        env = os.environ.copy()
        env.update(config.extra.get("env", {}))

        self._proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            cwd=config.cwd,
            env=env,
            bufsize=1,
        )

        # Start background reader
        self._read_task = asyncio.create_task(self._read_loop())

        # Initialize the app-server protocol
        resp = await self._request("initialize", {
            "clientInfo": {
                "name": "duckdome",
                "title": "DuckDome",
                "version": "0.1.0",
            },
            "capabilities": {
                "experimentalApi": True,
            },
        })
        await self._notify("initialized")
        logger.info("Codex app-server initialized for agent %s", agent_id)

        # Start a thread
        thread_resp = await self._request("thread/start", {
            "cwd": config.cwd,
        })
        thread = thread_resp.get("thread", {})
        self._thread_id = thread.get("id") or thread.get("threadId")
        logger.info("Codex thread started: %s", self._thread_id)

        self._status = AgentStatus.IDLE
        self._emit(self.STATUS_CHANGE, StatusChangeEvent(
            agent_id=agent_id,
            agent_type="codex",
            channel_id=config.channel_id,
            status=AgentStatus.IDLE,
        ))

    async def stop(self) -> None:
        # Fail all pending futures so nothing hangs
        self._fail_pending_futures("Bridge stopping")

        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        if self._proc:
            proc = self._proc
            self._proc = None
            if proc.stdin:
                proc.stdin.close()
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                proc.kill()

        self._status = AgentStatus.OFFLINE
        if self._config:
            self._emit(self.STATUS_CHANGE, StatusChangeEvent(
                agent_id=self._agent_id,
                agent_type="codex",
                channel_id=self._config.channel_id,
                status=AgentStatus.OFFLINE,
            ))

    def _fail_pending_futures(self, reason: str) -> None:
        err = RuntimeError(reason)
        for fut in self._pending_requests.values():
            if not fut.done():
                fut.set_exception(err)
        self._pending_requests.clear()
        for fut in self._pending_approvals.values():
            if not fut.done():
                fut.set_exception(err)
        self._pending_approvals.clear()

    # ------------------------------------------------------------------
    # Communication
    # ------------------------------------------------------------------

    async def send_prompt(self, text: str, channel_id: str, sender: str) -> None:
        if not self._thread_id:
            raise RuntimeError("No active Codex thread")

        self._status = AgentStatus.WORKING
        self._emit(self.STATUS_CHANGE, StatusChangeEvent(
            agent_id=self._agent_id,
            agent_type="codex",
            channel_id=channel_id,
            status=AgentStatus.WORKING,
        ))

        resp = await self._request("turn/start", {
            "threadId": self._thread_id,
            "input": [{"type": "text", "text": text}],
        })
        turn = resp.get("turn", {})
        self._active_turn_id = turn.get("id") or turn.get("turnId")

    async def interrupt(self) -> None:
        if not self._thread_id or not self._active_turn_id:
            return
        await self._request("turn/interrupt", {
            "threadId": self._thread_id,
            "turnId": self._active_turn_id,
        })

    # ------------------------------------------------------------------
    # Approval
    # ------------------------------------------------------------------

    async def approve(self, approval_id: str) -> None:
        fut = self._pending_approvals.pop(approval_id, None)
        if fut and not fut.done():
            fut.set_result({"decision": "accept"})

    async def deny(self, approval_id: str, reason: str) -> None:
        fut = self._pending_approvals.pop(approval_id, None)
        if fut and not fut.done():
            fut.set_result({"decision": "decline"})

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def get_status(self) -> AgentStatus:
        return self._status

    # ------------------------------------------------------------------
    # JSON-RPC transport
    # ------------------------------------------------------------------

    async def _write(self, msg: _JsonDict) -> None:
        if not self._proc or not self._proc.stdin:
            raise RuntimeError("Codex process not running")
        line = json.dumps(msg) + "\n"
        async with self._write_lock:
            await asyncio.to_thread(self._proc.stdin.write, line)
            await asyncio.to_thread(self._proc.stdin.flush)

    async def _request(
        self, method: str, params: _JsonDict, timeout: float = 30.0,
    ) -> _JsonDict:
        request_id = str(uuid.uuid4())
        fut: asyncio.Future[_JsonDict] = asyncio.get_running_loop().create_future()
        self._pending_requests[request_id] = fut
        await self._write(_make_request(method, params, request_id))
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            raise RuntimeError(f"Codex request {method} timed out after {timeout}s")

    async def _notify(self, method: str, params: _JsonDict | None = None) -> None:
        await self._write(_make_notification(method, params))

    async def _read_loop(self) -> None:
        """Background task that reads JSON-RPC messages from stdout."""
        try:
            while self._proc and self._proc.stdout:
                line = await asyncio.to_thread(self._proc.stdout.readline)
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Non-JSON from codex stdout: %s", line[:200])
                    continue

                await self._handle_message(msg)
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("Codex read loop crashed")
        finally:
            self._fail_pending_futures("Codex process exited")
            if self._status != AgentStatus.OFFLINE:
                self._status = AgentStatus.OFFLINE
                if self._config:
                    self._emit(self.STATUS_CHANGE, StatusChangeEvent(
                        agent_id=self._agent_id,
                        agent_type="codex",
                        channel_id=self._config.channel_id,
                        status=AgentStatus.OFFLINE,
                    ))

    async def _handle_message(self, msg: _JsonDict) -> None:
        # Response to our request
        if "id" in msg and "method" not in msg:
            request_id = msg["id"]
            fut = self._pending_requests.pop(request_id, None)
            if fut and not fut.done():
                if "error" in msg:
                    fut.set_exception(RuntimeError(
                        f"Codex JSON-RPC error: {msg['error']}"
                    ))
                else:
                    fut.set_result(msg.get("result", {}))
            return

        # Server request (needs our response — e.g. approval)
        if "id" in msg and "method" in msg:
            await self._handle_server_request(msg)
            return

        # Notification (no id)
        if "method" in msg and "id" not in msg:
            self._handle_notification(msg["method"], msg.get("params", {}))
            return

    async def _handle_server_request(self, msg: _JsonDict) -> None:
        method = msg["method"]
        params = msg.get("params", {})
        request_id = msg["id"]

        if method in (
            "item/commandExecution/requestApproval",
            "item/applyPatch/requestApproval",
        ):
            approval_id = params.get("approvalId") or params.get("itemId") or str(uuid.uuid4())
            command = params.get("command", "")
            tool_name = "local_shell" if "commandExecution" in method else "apply_patch"

            fut: asyncio.Future[_JsonDict] = asyncio.get_running_loop().create_future()
            self._pending_approvals[approval_id] = fut

            self._emit(self.APPROVAL_REQUEST, ApprovalRequestEvent(
                agent_id=self._agent_id,
                agent_type="codex",
                channel_id=self._config.channel_id if self._config else "",
                approval_id=approval_id,
                tool_name=tool_name,
                tool_input=params,
                description=command or f"{tool_name} request",
            ))

            try:
                decision = await asyncio.wait_for(fut, timeout=600)
            except asyncio.TimeoutError:
                decision = {"decision": "decline"}

            await self._write(_make_response(request_id, decision))
            return

        # Unknown server request — auto-decline
        logger.warning("Unknown Codex server request: %s", method)
        await self._write(_make_response(request_id, {}))

    # ------------------------------------------------------------------
    # Notification handlers
    # ------------------------------------------------------------------

    def _handle_notification(self, method: str, params: _JsonDict) -> None:
        channel_id = self._config.channel_id if self._config else ""

        match method:
            case "turn/started":
                self._active_turn_id = params.get("turnId") or params.get("turn", {}).get("id")
                self._status = AgentStatus.WORKING
                self._emit(self.STATUS_CHANGE, StatusChangeEvent(
                    agent_id=self._agent_id,
                    agent_type="codex",
                    channel_id=channel_id,
                    status=AgentStatus.WORKING,
                ))

            case "turn/completed":
                self._active_turn_id = None
                self._status = AgentStatus.IDLE
                self._emit(self.STATUS_CHANGE, StatusChangeEvent(
                    agent_id=self._agent_id,
                    agent_type="codex",
                    channel_id=channel_id,
                    status=AgentStatus.IDLE,
                ))

            case "item/agentMessage/delta":
                self._emit(self.MESSAGE_DELTA, AgentMessageDeltaEvent(
                    agent_id=self._agent_id,
                    agent_type="codex",
                    channel_id=channel_id,
                    delta=params.get("delta", ""),
                ))

            case "item/started":
                item_type = params.get("type", "")
                item_id = params.get("itemId", "")
                if item_type in ("commandExecution", "localShell", "mcpToolCall"):
                    self._emit(self.TOOL_CALL, ToolCallEvent(
                        agent_id=self._agent_id,
                        agent_type="codex",
                        channel_id=channel_id,
                        tool_name=params.get("name", item_type),
                        tool_input=params,
                        call_id=item_id,
                    ))

            case "item/completed":
                item_type = params.get("type", "")
                item_id = params.get("itemId", "")
                if item_type == "agentMessage":
                    text_parts = []
                    for content in params.get("content", []):
                        if isinstance(content, dict) and content.get("type") == "text":
                            text_parts.append(content.get("text", ""))
                    if text_parts:
                        self._emit(self.MESSAGE, AgentMessageEvent(
                            agent_id=self._agent_id,
                            agent_type="codex",
                            channel_id=channel_id,
                            text="\n".join(text_parts),
                        ))
                elif item_type in ("commandExecution", "localShell", "mcpToolCall"):
                    self._emit(self.TOOL_RESULT, ToolResultEvent(
                        agent_id=self._agent_id,
                        agent_type="codex",
                        channel_id=channel_id,
                        tool_name=params.get("name", item_type),
                        call_id=item_id,
                        success=params.get("status") == "completed",
                        output=params.get("output", ""),
                    ))

            case "error":
                self._emit(self.ERROR, ErrorEvent(
                    agent_id=self._agent_id,
                    agent_type="codex",
                    channel_id=channel_id,
                    error=params.get("message", "Unknown error"),
                    details=params.get("codexErrorInfo"),
                ))

            case _:
                logger.debug("Unhandled Codex notification: %s", method)
