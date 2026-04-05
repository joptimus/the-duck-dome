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
        fut = self._pending_approvals.pop(approval_id, None)
        if fut and not fut.done():
            opt = getattr(fut, "_gemini_allow_option", {"optionId": "allow_once"})
            fut.set_result({"optionId": opt["optionId"]})

    async def deny(self, approval_id: str, reason: str) -> None:
        fut = self._pending_approvals.pop(approval_id, None)
        if fut and not fut.done():
            opt = getattr(fut, "_gemini_reject_option", {"optionId": "reject_once"})
            fut.set_result({"optionId": opt["optionId"]})

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
            raise RuntimeError("Gemini process not running")
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
            raise RuntimeError(f"Gemini request {method} timed out after {timeout}s")

    async def _notify(self, method: str, params: _JsonDict | None = None) -> None:
        await self._write(_make_notification(method, params))

    async def _read_loop(self) -> None:
        """Background task that reads JSON-RPC messages from gemini's stdout."""
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
                    logger.warning("Non-JSON from gemini stdout: %s", line[:200])
                    continue
                await self._handle_message(msg)
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("Gemini read loop crashed")
        finally:
            self._fail_pending_futures("Gemini process exited")
            if self._status != AgentStatus.OFFLINE:
                self._status = AgentStatus.OFFLINE
                if self._config:
                    self._emit(self.STATUS_CHANGE, StatusChangeEvent(
                        agent_id=self._agent_id,
                        agent_type="gemini",
                        channel_id=self._config.channel_id,
                        status=AgentStatus.OFFLINE,
                    ))

    async def _handle_message(self, msg: _JsonDict) -> None:
        # Response to our request (has id, no method)
        if "id" in msg and "method" not in msg:
            request_id = msg["id"]
            fut = self._pending_requests.pop(request_id, None)
            if fut and not fut.done():
                if "error" in msg:
                    fut.set_exception(RuntimeError(
                        f"Gemini JSON-RPC error: {msg['error']}"
                    ))
                else:
                    fut.set_result(msg.get("result", {}))
            return

        # Server request (has id and method — needs our response)
        if "id" in msg and "method" in msg:
            await self._handle_server_request(msg)
            return

        # Notification (has method, no id)
        if "method" in msg and "id" not in msg:
            self._handle_notification(msg["method"], msg.get("params", {}))
            return

    async def _handle_server_request(self, msg: _JsonDict) -> None:
        """Handle an incoming JSON-RPC request from gemini (approvals, fs proxy)."""
        method = msg.get("method", "")
        params = msg.get("params", {}) or {}
        request_id = msg["id"]

        if method == "session/request_permission":
            await self._handle_permission_request(request_id, params)
            return

        if method == "fs/read_text_file":
            await self._handle_fs_read(request_id, params)
            return

        if method == "fs/write_text_file":
            await self._handle_fs_write(request_id, params)
            return

        logger.warning("Unhandled Gemini server request: %s", method)
        await self._write(_make_error_response(request_id, -32601, "Method not implemented"))

    async def _handle_permission_request(self, request_id: str, params: _JsonDict) -> None:
        tool_call = params.get("toolCall", {}) or {}
        approval_id = tool_call.get("toolCallId") or str(uuid.uuid4())
        tool_name = tool_call.get("title") or tool_call.get("kind", "tool")
        tool_input = tool_call.get("rawInput", {}) or {}
        options = params.get("options", []) or []

        allow_option = next(
            (o for o in options if o.get("kind") == "allow_once"),
            options[0] if options else {"optionId": "allow"},
        )
        reject_option = next(
            (o for o in options if o.get("kind") == "reject_once"),
            options[-1] if options else {"optionId": "reject"},
        )

        fut: asyncio.Future[_JsonDict] = asyncio.get_running_loop().create_future()
        self._pending_approvals[approval_id] = fut
        fut._gemini_allow_option = allow_option  # type: ignore[attr-defined]
        fut._gemini_reject_option = reject_option  # type: ignore[attr-defined]

        self._emit(self.APPROVAL_REQUEST, ApprovalRequestEvent(
            agent_id=self._agent_id,
            agent_type="gemini",
            channel_id=self._config.channel_id if self._config else "",
            approval_id=approval_id,
            tool_name=tool_name,
            tool_input=tool_input,
            description=tool_call.get("title", tool_name),
        ))

        try:
            decision = await asyncio.wait_for(fut, timeout=600)
        except asyncio.TimeoutError:
            decision = {"optionId": reject_option.get("optionId", "reject_once")}
            logger.warning("Gemini approval timed out: approval_id=%s", approval_id)

        await self._write(_make_response(request_id, {
            "outcome": {"outcome": "selected", "optionId": decision["optionId"]},
        }))

    async def _handle_fs_read(self, request_id: str, params: _JsonDict) -> None:
        await self._write(_make_error_response(request_id, -32601, "fs/read_text_file not yet implemented"))

    async def _handle_fs_write(self, request_id: str, params: _JsonDict) -> None:
        await self._write(_make_error_response(request_id, -32601, "fs/write_text_file not yet implemented"))

    def _handle_notification(self, method: str, params: _JsonDict) -> None:
        """Handle a JSON-RPC notification from gemini.

        Currently only ``session/update`` is surfaced; other methods are
        logged at debug and dropped.
        """
        if method != "session/update":
            logger.debug("Unhandled Gemini notification: %s", method)
            return

        channel_id = self._config.channel_id if self._config else ""
        update = params.get("update", {}) or {}
        kind = update.get("sessionUpdate", "")

        if kind in ("agent_message_chunk", "agent_thought_chunk"):
            content = update.get("content", {}) or {}
            text = ""
            if isinstance(content, dict) and content.get("type") == "text":
                text = content.get("text", "") or ""
            if text:
                self._emit(self.MESSAGE_DELTA, AgentMessageDeltaEvent(
                    agent_id=self._agent_id,
                    agent_type="gemini",
                    channel_id=channel_id,
                    delta=text,
                ))
            return

        if kind == "tool_call":
            tool_name = update.get("title") or update.get("kind", "tool")
            self._emit(self.TOOL_CALL, ToolCallEvent(
                agent_id=self._agent_id,
                agent_type="gemini",
                channel_id=channel_id,
                tool_name=tool_name,
                tool_input=update.get("rawInput", {}) or {},
                call_id=update.get("toolCallId", ""),
            ))
            return

        if kind == "tool_call_update":
            status = update.get("status", "")
            if status not in ("completed", "failed"):
                return  # in_progress and other intermediates are ignored
            raw_output = update.get("rawOutput", {}) or {}
            if isinstance(raw_output, dict):
                output_text = (
                    raw_output.get("stdout")
                    or raw_output.get("error")
                    or (json.dumps(raw_output) if raw_output else "")
                )
            else:
                output_text = str(raw_output)
            self._emit(self.TOOL_RESULT, ToolResultEvent(
                agent_id=self._agent_id,
                agent_type="gemini",
                channel_id=channel_id,
                tool_name=update.get("title", "") or update.get("kind", ""),
                call_id=update.get("toolCallId", ""),
                success=status == "completed",
                output=output_text or "",
            ))
            return

        # user_message_chunk, available_commands_update, current_mode_update,
        # plan, and any future kinds are intentionally ignored in v1.
        logger.debug("Ignoring Gemini session/update kind: %s", kind)

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
