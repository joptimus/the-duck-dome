# GeminiBridge Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a first-class `GeminiBridge` that controls Gemini CLI via its ACP (Agent Client Protocol) mode over stdio JSON-RPC, mirroring the existing `CodexBridge`, so Gemini becomes a peer of Claude and Codex in DuckDome's bridge architecture.

**Architecture:** `GeminiBridge` extends `AgentBridge` (same base as `ClaudeBridge` / `CodexBridge`). It spawns `gemini --acp`, speaks JSON-RPC 2.0 over the subprocess's stdin/stdout, normalizes ACP `session/update` notifications and `session/request_permission` server-requests into DuckDome's unified event model, and implements a pass-through filesystem proxy guarded to the agent's `cwd`. Manager routing is extended to create a `GeminiBridge` when `agent_type == "gemini"`. The legacy one-shot `runner/gemini.py::GeminiExecutor` stays in place as a fallback until live verification.

**Tech Stack:** Python 3.11+, `asyncio`, `subprocess`, stdlib `json`, `uuid`, `pathlib`, `pytest`. No new dependencies. Reference implementation pattern: `backend/src/duckdome/bridges/codex_bridge.py`.

**Design reference:** `docs/plans/2026-04-04-gemini-bridge-integration.md` (committed on branch `docs/gemini-bridge-design`, also present in this worktree's git history).

**Known baseline failures (not introduced by this work):** 5 pre-existing test failures in `tests/test_mcp_bridge.py` (4) and `tests/test_main_startup.py` (1), inherited from the parent branch. Ignore these when judging correctness — any *additional* failure after a task is a regression we own.

---

## Prerequisites Check (do once before Task 1)

**Step P.1:** Confirm you're in the right worktree and branch.

Run: `pwd && git branch --show-current`
Expected: path ends in `feature-gemini-bridge`, branch is `feature/gemini-bridge`.

**Step P.2:** Confirm backend deps are installed.

Run: `cd backend && uv run python -c 'import duckdome.bridges.codex_bridge' && echo OK`
Expected: `OK`.

**Step P.3:** Confirm the baseline failure set matches expected.

Run: `cd backend && uv run pytest -q 2>&1 | tail -15`
Expected: `5 failed, 381 passed`. The 5 failing tests are all in `test_mcp_bridge.py` or `test_main_startup.py`. If a different set fails, stop and investigate before starting.

**Step P.4:** Confirm `gemini` binary is on PATH (needed for the live reference run in Task 1 and for the `shutil.which` lookup in production code).

Run: `which gemini && gemini --version 2>&1`
Expected: a path and a version string. If missing, tell the user and stop.

---

## Task 0: Capture an ACP reference transcript from the real `gemini --acp`

**Why first:** The ACP wire method names (`session/new` vs `session.new`, exact param shapes, update types) are not fully documented in vendored code and must be verified against the real binary. A single reference transcript will pin down the exact wire shapes so every subsequent task codes against facts, not guesses.

**Files:**
- Create: `docs/plans/notes/acp-wire-transcript.md` (checked-in reference)

**Step 0.1: Record a minimal handshake + prompt transcript.**

Run (from repo root, outside pytest):
```bash
cd /tmp && mkdir -p gemini-acp-probe && cd gemini-acp-probe && \
python3 - <<'PY'
import json, subprocess, threading, time, sys

proc = subprocess.Popen(
    ["gemini", "--acp"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, bufsize=1,
)
log = []
def pump(name, stream):
    for line in stream:
        log.append((name, line.rstrip()))
        print(f"<<{name}>> {line.rstrip()}", flush=True)
threading.Thread(target=pump, args=("stdout", proc.stdout), daemon=True).start()
threading.Thread(target=pump, args=("stderr", proc.stderr), daemon=True).start()

def send(msg):
    line = json.dumps(msg) + "\n"
    print(f">>send>> {line.strip()}", flush=True)
    proc.stdin.write(line); proc.stdin.flush()

# 1. initialize — params per acp spec. Try the canonical shape.
send({"jsonrpc":"2.0","id":"1","method":"initialize",
      "params":{"protocolVersion":1,
                "clientCapabilities":{"fs":{"readTextFile":True,"writeTextFile":True}}}})
time.sleep(1)

# 2. newSession
send({"jsonrpc":"2.0","id":"2","method":"session/new",
      "params":{"cwd":"/tmp/gemini-acp-probe","mcpServers":[]}})
time.sleep(2)

# 3. Terminate
proc.terminate()
try: proc.wait(timeout=3)
except Exception: proc.kill()
PY
```

**Expected observations to capture into `docs/plans/notes/acp-wire-transcript.md`:**
- Exact method name for `initialize` response shape
- Exact method name for session creation (`session/new` vs `newSession` vs other)
- Whether auth succeeds automatically from env (`GEMINI_API_KEY` or pre-existing OAuth creds) or whether `authenticate` is required first
- Any error responses and their codes/messages

**Step 0.2: Save the transcript.**

Write the captured stdout/stderr log (both the `>>send>>` and `<<stdout>>/<<stderr>>` lines) to `docs/plans/notes/acp-wire-transcript.md` with a short header:
```markdown
# ACP Wire Transcript (gemini --acp, <version>, captured YYYY-MM-DD)

Reference for GeminiBridge implementation. Exact wire shapes observed from the real binary.

## Handshake
<paste log>

## Observations
- initialize method name: ...
- newSession method name: ...
- sessionId returned at: response.result.<path>
- Auth behavior on env-only: ...
```

**Step 0.3: Commit the transcript.**

```bash
cd /Users/james/.config/superpowers/worktrees/the-duck-dome/feature-gemini-bridge
git add docs/plans/notes/acp-wire-transcript.md
git commit -m "docs(gemini): capture ACP wire transcript for bridge reference"
```

**If Task 0 fails** (gemini refuses to start, auth required, different method names than expected): STOP and report findings to the user. Do not proceed to Task 1 until wire shapes are known — otherwise every subsequent task is guesswork.

---

## Task 1: Module skeleton + unit-test scaffolding

**Files:**
- Create: `backend/src/duckdome/bridges/gemini_bridge.py`
- Modify: `backend/src/duckdome/bridges/__init__.py`
- Modify: `backend/tests/test_bridges.py` (add new section header)

**Step 1.1: Write the failing test — class exists and is an AgentBridge.**

Add to `backend/tests/test_bridges.py` at the end of the file:

```python
# ===========================================================================
# Test: GeminiBridge notification dispatch
# ===========================================================================

from duckdome.bridges.gemini_bridge import GeminiBridge


def _make_gemini_bridge() -> GeminiBridge:
    bridge = GeminiBridge()
    bridge._agent_id = "gemini--test"
    bridge._config = AgentConfig(agent_type="gemini", channel_id="general", cwd="/tmp")
    return bridge


class TestGeminiBridgeConstruction:
    def test_is_agent_bridge(self):
        bridge = _make_gemini_bridge()
        assert isinstance(bridge, AgentBridge)

    def test_initial_state(self):
        bridge = _make_gemini_bridge()
        assert bridge._session_id is None
        assert bridge._status == AgentStatus.OFFLINE
```

**Step 1.2: Run to verify failure.**

Run: `cd backend && uv run pytest tests/test_bridges.py::TestGeminiBridgeConstruction -v`
Expected: `ImportError: cannot import name 'GeminiBridge'` or `ModuleNotFoundError`.

**Step 1.3: Create the module skeleton.**

Create `backend/src/duckdome/bridges/gemini_bridge.py`:

```python
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

    # Methods filled in by later tasks.

    async def start(self, agent_id: str, config: AgentConfig) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError

    async def send_prompt(self, text: str, channel_id: str, sender: str) -> None:
        raise NotImplementedError

    async def interrupt(self) -> None:
        raise NotImplementedError

    async def approve(self, approval_id: str) -> None:
        raise NotImplementedError

    async def deny(self, approval_id: str, reason: str) -> None:
        raise NotImplementedError

    async def get_status(self) -> AgentStatus:
        return self._status
```

**Step 1.4: Export from package.**

Edit `backend/src/duckdome/bridges/__init__.py` — add `from duckdome.bridges.gemini_bridge import GeminiBridge` to whatever pattern the file already uses. Read the file first to see its current shape.

**Step 1.5: Run the test again — should pass.**

Run: `cd backend && uv run pytest tests/test_bridges.py::TestGeminiBridgeConstruction -v`
Expected: `2 passed`.

**Step 1.6: Commit.**

```bash
git add backend/src/duckdome/bridges/gemini_bridge.py \
        backend/src/duckdome/bridges/__init__.py \
        backend/tests/test_bridges.py
git commit -m "feat(gemini-bridge): add GeminiBridge skeleton"
```

---

## Task 2: JSON-RPC transport helpers (_write, _request, _notify, _read_loop)

**Files:**
- Modify: `backend/src/duckdome/bridges/gemini_bridge.py`
- Modify: `backend/tests/test_bridges.py`

**Step 2.1: Write the failing tests.** Add to `test_bridges.py`:

```python
class TestGeminiBridgeTransport:
    def test_response_resolves_pending_future(self):
        async def _run():
            bridge = _make_gemini_bridge()
            fut = asyncio.get_running_loop().create_future()
            bridge._pending_requests["req-1"] = fut
            await bridge._handle_message({"id": "req-1", "result": {"sessionId": "s1"}})
            assert fut.done()
            assert fut.result() == {"sessionId": "s1"}
        asyncio.run(_run())

    def test_error_response_raises(self):
        async def _run():
            bridge = _make_gemini_bridge()
            fut = asyncio.get_running_loop().create_future()
            bridge._pending_requests["req-2"] = fut
            await bridge._handle_message({"id": "req-2", "error": {"code": -32000, "message": "auth"}})
            assert fut.done()
            with pytest.raises(RuntimeError, match="JSON-RPC error"):
                fut.result()
        asyncio.run(_run())

    def test_notification_dispatches(self):
        async def _run():
            bridge = _make_gemini_bridge()
            calls = []
            bridge._handle_notification = lambda m, p: calls.append((m, p))  # type: ignore
            await bridge._handle_message({
                "method": "session/update",
                "params": {"sessionId": "s1", "update": {"sessionUpdate": "agent_message_chunk"}},
            })
            assert calls == [("session/update", {"sessionId": "s1", "update": {"sessionUpdate": "agent_message_chunk"}})]
        asyncio.run(_run())
```

**Step 2.2: Run to verify failure.** Expected: `AttributeError: 'GeminiBridge' object has no attribute '_handle_message'`.

**Step 2.3: Implement the transport layer.** Add to `gemini_bridge.py` (copy the shape from `codex_bridge.py` lines 300–382 with `_handle_server_request` stubbed for Task 4):

```python
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

    async def _read_loop(self) -> None:
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
        # Response to our request
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

        # Server request (needs our response — approval or fs proxy)
        if "id" in msg and "method" in msg:
            await self._handle_server_request(msg)
            return

        # Notification (no id)
        if "method" in msg and "id" not in msg:
            self._handle_notification(msg["method"], msg.get("params", {}))
            return

    async def _handle_server_request(self, msg: _JsonDict) -> None:
        # Filled in by Task 4 (approvals) and Task 5 (fs proxy).
        request_id = msg["id"]
        logger.warning("Unhandled Gemini server request: %s", msg.get("method"))
        await self._write(_make_error_response(request_id, -32601, "Method not implemented"))

    def _handle_notification(self, method: str, params: _JsonDict) -> None:
        # Filled in by Task 3.
        logger.debug("Unhandled Gemini notification: %s", method)

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
```

**Step 2.4: Run tests.** Expected: 3 passing in `TestGeminiBridgeTransport`.

**Step 2.5: Commit.**

```bash
git add backend/src/duckdome/bridges/gemini_bridge.py backend/tests/test_bridges.py
git commit -m "feat(gemini-bridge): add JSON-RPC transport layer"
```

---

## Task 3: `session/update` notification handler (event mapping)

**Files:**
- Modify: `backend/src/duckdome/bridges/gemini_bridge.py`
- Modify: `backend/tests/test_bridges.py`

**Step 3.1: Write failing tests** covering the five `sessionUpdate` kinds from ACP (ref: `DevApps/gemini-cli/packages/cli/src/acp/acpClient.ts` lines 611–1730):

```python
class TestGeminiBridgeNotifications:
    def test_agent_message_chunk_emits_delta(self):
        bridge = _make_gemini_bridge()
        events = _collect(bridge, bridge.MESSAGE_DELTA)
        bridge._handle_notification("session/update", {
            "sessionId": "s1",
            "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": "hello"},
            },
        })
        assert len(events) == 1
        assert events[0].delta == "hello"

    def test_agent_thought_chunk_emits_delta(self):
        bridge = _make_gemini_bridge()
        events = _collect(bridge, bridge.MESSAGE_DELTA)
        bridge._handle_notification("session/update", {
            "sessionId": "s1",
            "update": {
                "sessionUpdate": "agent_thought_chunk",
                "content": {"type": "text", "text": "thinking..."},
            },
        })
        assert len(events) == 1
        assert events[0].delta == "thinking..."

    def test_tool_call_emits_tool_call_event(self):
        bridge = _make_gemini_bridge()
        events = _collect(bridge, bridge.TOOL_CALL)
        bridge._handle_notification("session/update", {
            "sessionId": "s1",
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "tc1",
                "title": "run shell",
                "kind": "execute",
                "status": "pending",
                "rawInput": {"command": "ls"},
            },
        })
        assert len(events) == 1
        assert events[0].call_id == "tc1"
        assert events[0].tool_name == "run shell"
        assert events[0].tool_input == {"command": "ls"}

    def test_tool_call_update_completed_emits_tool_result(self):
        bridge = _make_gemini_bridge()
        events = _collect(bridge, bridge.TOOL_RESULT)
        bridge._handle_notification("session/update", {
            "sessionId": "s1",
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "tc1",
                "status": "completed",
                "rawOutput": {"stdout": "hello"},
            },
        })
        assert len(events) == 1
        assert events[0].call_id == "tc1"
        assert events[0].success is True

    def test_tool_call_update_failed_emits_failed_result(self):
        bridge = _make_gemini_bridge()
        events = _collect(bridge, bridge.TOOL_RESULT)
        bridge._handle_notification("session/update", {
            "sessionId": "s1",
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "tc1",
                "status": "failed",
                "rawOutput": {"error": "boom"},
            },
        })
        assert len(events) == 1
        assert events[0].success is False

    def test_tool_call_update_in_progress_does_not_emit_result(self):
        bridge = _make_gemini_bridge()
        events = _collect(bridge, bridge.TOOL_RESULT)
        bridge._handle_notification("session/update", {
            "sessionId": "s1",
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "tc1",
                "status": "in_progress",
            },
        })
        assert events == []

    def test_available_commands_update_ignored(self):
        bridge = _make_gemini_bridge()
        all_events = []
        for et in (bridge.MESSAGE, bridge.MESSAGE_DELTA, bridge.TOOL_CALL, bridge.TOOL_RESULT):
            bridge.on(et, lambda e, _et=et: all_events.append((_et, e)))
        bridge._handle_notification("session/update", {
            "sessionId": "s1",
            "update": {"sessionUpdate": "available_commands_update", "availableCommands": []},
        })
        assert all_events == []

    def test_unknown_notification_does_not_crash(self):
        bridge = _make_gemini_bridge()
        bridge._handle_notification("some/unknown/method", {})
```

**Step 3.2: Run to verify failure.** Expected: all fail because `_handle_notification` is a no-op stub.

**Step 3.3: Implement `_handle_notification`.** Replace the stub in `gemini_bridge.py`:

```python
    def _handle_notification(self, method: str, params: _JsonDict) -> None:
        if method != "session/update":
            logger.debug("Unhandled Gemini notification: %s", method)
            return

        channel_id = self._config.channel_id if self._config else ""
        update = params.get("update", {}) or {}
        kind = update.get("sessionUpdate", "")

        if kind in ("agent_message_chunk", "agent_thought_chunk"):
            content = update.get("content", {}) or {}
            text = content.get("text", "") if isinstance(content, dict) else ""
            if text:
                self._emit(self.MESSAGE_DELTA, AgentMessageDeltaEvent(
                    agent_id=self._agent_id,
                    agent_type="gemini",
                    channel_id=channel_id,
                    delta=text,
                ))
            return

        if kind == "tool_call":
            self._emit(self.TOOL_CALL, ToolCallEvent(
                agent_id=self._agent_id,
                agent_type="gemini",
                channel_id=channel_id,
                tool_name=update.get("title") or update.get("kind", "tool"),
                tool_input=update.get("rawInput", {}) or {},
                call_id=update.get("toolCallId", ""),
            ))
            return

        if kind == "tool_call_update":
            status = update.get("status", "")
            if status not in ("completed", "failed"):
                return  # in_progress and other intermediates ignored
            raw_output = update.get("rawOutput", {}) or {}
            output_text = (
                raw_output.get("stdout")
                or raw_output.get("error")
                or json.dumps(raw_output) if raw_output else ""
            )
            self._emit(self.TOOL_RESULT, ToolResultEvent(
                agent_id=self._agent_id,
                agent_type="gemini",
                channel_id=channel_id,
                tool_name=update.get("title", ""),
                call_id=update.get("toolCallId", ""),
                success=status == "completed",
                output=output_text or "",
            ))
            return

        # user_message_chunk, available_commands_update, current_mode_update, plan → ignored v1
        logger.debug("Ignoring Gemini session/update kind: %s", kind)
```

**Step 3.4: Run tests.** Expected: all 8 in `TestGeminiBridgeNotifications` pass.

**Step 3.5: Commit.**

```bash
git add backend/src/duckdome/bridges/gemini_bridge.py backend/tests/test_bridges.py
git commit -m "feat(gemini-bridge): map session/update notifications to unified events"
```

---

## Task 4: Approval flow (`session/request_permission`)

**Files:**
- Modify: `backend/src/duckdome/bridges/gemini_bridge.py`
- Modify: `backend/tests/test_bridges.py`

**Step 4.1: Write failing tests.**

```python
class TestGeminiBridgeApproval:
    def test_request_permission_emits_approval_event(self):
        async def _run():
            bridge = _make_gemini_bridge()
            # Stub _write so we capture the response without a real process
            sent = []
            async def fake_write(m): sent.append(m)
            bridge._write = fake_write  # type: ignore
            events = _collect(bridge, bridge.APPROVAL_REQUEST)

            # Schedule an immediate approve after the server-request parks
            async def approve_soon():
                # Wait until the pending approval is registered
                while not bridge._pending_approvals:
                    await asyncio.sleep(0.01)
                approval_id = next(iter(bridge._pending_approvals))
                await bridge.approve(approval_id)
            asyncio.create_task(approve_soon())

            await bridge._handle_server_request({
                "jsonrpc": "2.0",
                "id": "srv-1",
                "method": "session/request_permission",
                "params": {
                    "sessionId": "s1",
                    "toolCall": {
                        "toolCallId": "tc1",
                        "title": "run shell",
                        "rawInput": {"command": "rm -rf /"},
                    },
                    "options": [
                        {"optionId": "allow_once", "name": "Allow once", "kind": "allow_once"},
                        {"optionId": "reject_once", "name": "Reject", "kind": "reject_once"},
                    ],
                },
            })

            assert len(events) == 1
            assert events[0].approval_id == "tc1"
            assert events[0].tool_name == "run shell"
            # Verify the JSON-RPC response sent back to gemini
            assert any(
                m.get("id") == "srv-1" and m.get("result", {}).get("outcome", {}).get("outcome") == "selected"
                for m in sent
            )
        asyncio.run(_run())

    def test_deny_selects_reject_option(self):
        async def _run():
            bridge = _make_gemini_bridge()
            sent = []
            async def fake_write(m): sent.append(m)
            bridge._write = fake_write  # type: ignore

            async def deny_soon():
                while not bridge._pending_approvals:
                    await asyncio.sleep(0.01)
                approval_id = next(iter(bridge._pending_approvals))
                await bridge.deny(approval_id, "nope")
            asyncio.create_task(deny_soon())

            await bridge._handle_server_request({
                "jsonrpc": "2.0",
                "id": "srv-2",
                "method": "session/request_permission",
                "params": {
                    "sessionId": "s1",
                    "toolCall": {"toolCallId": "tc2", "title": "bad", "rawInput": {}},
                    "options": [
                        {"optionId": "allow_once", "name": "Allow", "kind": "allow_once"},
                        {"optionId": "reject_once", "name": "Reject", "kind": "reject_once"},
                    ],
                },
            })

            reply = next(m for m in sent if m.get("id") == "srv-2")
            assert reply["result"]["outcome"]["optionId"] == "reject_once"
        asyncio.run(_run())
```

**Step 4.2: Run to verify failure.** Expected: approval tests fail because `_handle_server_request` currently returns method-not-found for everything.

**Step 4.3: Implement the approval path.** Replace `_handle_server_request` in `gemini_bridge.py`:

```python
    async def _handle_server_request(self, msg: _JsonDict) -> None:
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

        # Pick allow/reject option IDs by their `kind` field
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
        # Remember which option IDs map to approve/deny so approve/deny can resolve with the right payload.
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
```

Also add these stub FS handlers so `_handle_server_request` imports cleanly (real implementation in Task 5):

```python
    async def _handle_fs_read(self, request_id: str, params: _JsonDict) -> None:
        await self._write(_make_error_response(request_id, -32601, "fs/read_text_file not yet implemented"))

    async def _handle_fs_write(self, request_id: str, params: _JsonDict) -> None:
        await self._write(_make_error_response(request_id, -32601, "fs/write_text_file not yet implemented"))
```

**Step 4.4: Run tests.** Expected: both tests in `TestGeminiBridgeApproval` pass.

**Step 4.5: Commit.**

```bash
git add backend/src/duckdome/bridges/gemini_bridge.py backend/tests/test_bridges.py
git commit -m "feat(gemini-bridge): handle session/request_permission server requests"
```

---

## Task 5: FS proxy (`fs/read_text_file`, `fs/write_text_file`) with cwd guard

**Files:**
- Modify: `backend/src/duckdome/bridges/gemini_bridge.py`
- Modify: `backend/tests/test_bridges.py`

**Step 5.1: Write failing tests.**

```python
class TestGeminiBridgeFsProxy:
    def test_fs_read_inside_cwd(self, tmp_path):
        async def _run():
            target = tmp_path / "hello.txt"
            target.write_text("hi", encoding="utf-8")
            bridge = _make_gemini_bridge()
            bridge._config = AgentConfig(agent_type="gemini", channel_id="g", cwd=str(tmp_path))
            sent = []
            async def fake_write(m): sent.append(m)
            bridge._write = fake_write  # type: ignore

            await bridge._handle_server_request({
                "jsonrpc": "2.0", "id": "fs-1",
                "method": "fs/read_text_file",
                "params": {"sessionId": "s1", "path": str(target)},
            })
            reply = next(m for m in sent if m.get("id") == "fs-1")
            assert reply["result"]["content"] == "hi"
        asyncio.run(_run())

    def test_fs_read_outside_cwd_rejected(self, tmp_path):
        async def _run():
            bridge = _make_gemini_bridge()
            bridge._config = AgentConfig(agent_type="gemini", channel_id="g", cwd=str(tmp_path))
            sent = []
            async def fake_write(m): sent.append(m)
            bridge._write = fake_write  # type: ignore
            await bridge._handle_server_request({
                "jsonrpc": "2.0", "id": "fs-2",
                "method": "fs/read_text_file",
                "params": {"sessionId": "s1", "path": "/etc/passwd"},
            })
            reply = next(m for m in sent if m.get("id") == "fs-2")
            assert "error" in reply
        asyncio.run(_run())

    def test_fs_write_inside_cwd_creates_parent_dirs(self, tmp_path):
        async def _run():
            bridge = _make_gemini_bridge()
            bridge._config = AgentConfig(agent_type="gemini", channel_id="g", cwd=str(tmp_path))
            sent = []
            async def fake_write(m): sent.append(m)
            bridge._write = fake_write  # type: ignore
            target = tmp_path / "sub" / "out.txt"
            await bridge._handle_server_request({
                "jsonrpc": "2.0", "id": "fs-3",
                "method": "fs/write_text_file",
                "params": {"sessionId": "s1", "path": str(target), "content": "body"},
            })
            assert target.read_text(encoding="utf-8") == "body"
            reply = next(m for m in sent if m.get("id") == "fs-3")
            assert "error" not in reply
        asyncio.run(_run())

    def test_fs_write_outside_cwd_rejected(self, tmp_path):
        async def _run():
            bridge = _make_gemini_bridge()
            bridge._config = AgentConfig(agent_type="gemini", channel_id="g", cwd=str(tmp_path))
            sent = []
            async def fake_write(m): sent.append(m)
            bridge._write = fake_write  # type: ignore
            await bridge._handle_server_request({
                "jsonrpc": "2.0", "id": "fs-4",
                "method": "fs/write_text_file",
                "params": {"sessionId": "s1", "path": "/tmp/escape.txt", "content": "x"},
            })
            reply = next(m for m in sent if m.get("id") == "fs-4")
            assert "error" in reply
        asyncio.run(_run())
```

**Step 5.2: Run to verify failure.** Expected: all 4 fs tests fail with "not yet implemented" errors.

**Step 5.3: Implement the real handlers.** Replace the stubs:

```python
    def _resolve_fs_path(self, raw: str) -> Path:
        """Resolve and guard a path against the agent's cwd. Raises ValueError if escape attempt."""
        if not self._config or not self._config.cwd:
            raise ValueError("Bridge has no cwd configured")
        cwd = Path(self._config.cwd).resolve()
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = cwd / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(cwd)
        except ValueError:
            raise ValueError(f"Path {raw!r} escapes cwd {cwd}")
        return resolved

    async def _handle_fs_read(self, request_id: str, params: _JsonDict) -> None:
        try:
            path = self._resolve_fs_path(params.get("path", ""))
            content = path.read_text(encoding="utf-8")
            # Honor optional line/limit per ACP spec
            line = params.get("line")
            limit = params.get("limit")
            if line is not None or limit is not None:
                lines = content.splitlines(keepends=True)
                start = int(line) - 1 if line else 0
                end = start + int(limit) if limit else len(lines)
                content = "".join(lines[start:end])
            await self._write(_make_response(request_id, {"content": content}))
        except ValueError as e:
            await self._write(_make_error_response(request_id, -32602, str(e)))
        except (FileNotFoundError, PermissionError, OSError) as e:
            await self._write(_make_error_response(request_id, -32000, f"fs read failed: {e}"))

    async def _handle_fs_write(self, request_id: str, params: _JsonDict) -> None:
        try:
            path = self._resolve_fs_path(params.get("path", ""))
            content = params.get("content", "")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            await self._write(_make_response(request_id, {}))
        except ValueError as e:
            await self._write(_make_error_response(request_id, -32602, str(e)))
        except (PermissionError, OSError) as e:
            await self._write(_make_error_response(request_id, -32000, f"fs write failed: {e}"))
```

**Step 5.4: Run tests.** Expected: 4 passing in `TestGeminiBridgeFsProxy`.

**Step 5.5: Commit.**

```bash
git add backend/src/duckdome/bridges/gemini_bridge.py backend/tests/test_bridges.py
git commit -m "feat(gemini-bridge): add cwd-guarded fs proxy handlers"
```

---

## Task 6: Lifecycle — `start`, `stop`, `send_prompt`, `interrupt`

**IMPORTANT:** Method names and param shapes below are **draft guesses from ACP docs and the `acpClient.ts` source**. Before writing the implementation, re-read the `docs/plans/notes/acp-wire-transcript.md` captured in Task 0 and update this task's exact method names/params if they differ from what's written here. The most likely wire names are `initialize`, `session/new`, `session/prompt`, `session/cancel`, but the transcript is authoritative.

**Files:**
- Modify: `backend/src/duckdome/bridges/gemini_bridge.py`
- Modify: `backend/tests/test_bridges.py`

**Step 6.1: Write failing tests using a fake process pattern.** Because these methods drive real subprocess I/O, we test by monkey-patching `_write` and `_request` on the bridge instance:

```python
class TestGeminiBridgeLifecycle:
    def test_send_prompt_dispatches_session_prompt(self):
        async def _run():
            bridge = _make_gemini_bridge()
            bridge._session_id = "sess-1"
            bridge._status = AgentStatus.IDLE
            calls = []
            async def fake_request(method, params, timeout=30.0):
                calls.append((method, params))
                return {}
            bridge._request = fake_request  # type: ignore

            await bridge.send_prompt("do the thing", "general", "human")

            assert len(calls) == 1
            method, params = calls[0]
            assert method == "session/prompt"
            assert params["sessionId"] == "sess-1"
            # prompt payload shape: list of content blocks
            assert any(
                isinstance(b, dict) and b.get("type") == "text" and "do the thing" in b.get("text", "")
                for b in params.get("prompt", [])
            )
        asyncio.run(_run())

    def test_send_prompt_without_session_raises(self):
        async def _run():
            bridge = _make_gemini_bridge()
            with pytest.raises(RuntimeError, match="session"):
                await bridge.send_prompt("x", "ch", "s")
        asyncio.run(_run())

    def test_interrupt_dispatches_session_cancel(self):
        async def _run():
            bridge = _make_gemini_bridge()
            bridge._session_id = "sess-2"
            calls = []
            async def fake_request(method, params, timeout=30.0):
                calls.append((method, params))
                return {}
            bridge._request = fake_request  # type: ignore
            await bridge.interrupt()
            # cancel is a notification in ACP, but accept either request or notify pattern
            # If your transcript showed it as a notification, adjust this test and the impl.
            assert calls == [] or calls[0][0] == "session/cancel"
        asyncio.run(_run())

    def test_stop_is_idempotent_without_proc(self):
        async def _run():
            bridge = _make_gemini_bridge()
            await bridge.stop()  # no proc yet
            assert bridge._status == AgentStatus.OFFLINE
        asyncio.run(_run())
```

**Step 6.2: Run to verify failure.**

**Step 6.3: Implement `start`, `stop`, `send_prompt`, `interrupt`.** Adapt from `codex_bridge.py` lines 93–265:

```python
    async def start(self, agent_id: str, config: AgentConfig) -> None:
        self._agent_id = agent_id
        self._config = config

        gemini_bin = shutil.which("gemini")
        if gemini_bin is None:
            raise FileNotFoundError("gemini binary not found on PATH")

        args = [gemini_bin, "--acp"]
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
        logger.info(
            "Gemini bridge launch: agent=%s cwd=%s args=%s",
            agent_id, config.cwd, args,
        )

        self._read_task = asyncio.create_task(self._read_loop())

        try:
            # --- The exact method name / param shape below MUST match Task 0 transcript. ---
            await self._request("initialize", {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": True, "writeTextFile": True},
                },
            })
            mcp_servers = []
            if config.mcp_url:
                mcp_servers.append({
                    "name": "duckdome",
                    "url": config.mcp_url,
                })
            resp = await self._request("session/new", {
                "cwd": config.cwd,
                "mcpServers": mcp_servers,
            })
            self._session_id = resp.get("sessionId")
            if not self._session_id:
                raise RuntimeError(f"Gemini session/new returned no sessionId: {resp}")
            logger.info("Gemini session started: %s", self._session_id)
        except Exception:
            logger.exception("Gemini init failed for agent %s; cleaning up", agent_id)
            await self.stop()
            raise

        self._status = AgentStatus.IDLE
        self._emit(self.STATUS_CHANGE, StatusChangeEvent(
            agent_id=agent_id,
            agent_type="gemini",
            channel_id=config.channel_id,
            status=AgentStatus.IDLE,
        ))

    async def stop(self) -> None:
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
                loop = asyncio.get_running_loop()
                await asyncio.wait_for(
                    loop.run_in_executor(None, proc.wait),
                    timeout=2,
                )
            except (asyncio.TimeoutError, Exception):
                proc.kill()
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, proc.wait)

        self._status = AgentStatus.OFFLINE
        if self._config:
            self._emit(self.STATUS_CHANGE, StatusChangeEvent(
                agent_id=self._agent_id,
                agent_type="gemini",
                channel_id=self._config.channel_id,
                status=AgentStatus.OFFLINE,
            ))

    async def send_prompt(self, text: str, channel_id: str, sender: str) -> None:
        if not self._session_id:
            raise RuntimeError("No active Gemini session")

        self._status = AgentStatus.WORKING
        self._emit(self.STATUS_CHANGE, StatusChangeEvent(
            agent_id=self._agent_id,
            agent_type="gemini",
            channel_id=channel_id,
            status=AgentStatus.WORKING,
        ))

        await self._request("session/prompt", {
            "sessionId": self._session_id,
            "prompt": [{"type": "text", "text": text}],
        }, timeout=600.0)

        # session/prompt returns when the turn completes in ACP.
        self._status = AgentStatus.IDLE
        self._emit(self.STATUS_CHANGE, StatusChangeEvent(
            agent_id=self._agent_id,
            agent_type="gemini",
            channel_id=channel_id,
            status=AgentStatus.IDLE,
        ))

    async def interrupt(self) -> None:
        if not self._session_id:
            return
        # In ACP, cancel is typically a notification, not a request.
        # Adjust to match Task 0 transcript: if it's a request, change to self._request().
        try:
            await self._write(_make_request("session/cancel", {"sessionId": self._session_id}))
        except Exception:
            logger.exception("Gemini interrupt failed")
```

**Step 6.4: Run the four new tests.** Expected: 3 of 4 pass. `test_interrupt_dispatches_session_cancel` may need adjusting once the transcript confirms whether cancel is a notification (no id, no response expected) or a request. Adjust test + impl to match the transcript's observed behavior, then re-run.

**Step 6.5: Commit.**

```bash
git add backend/src/duckdome/bridges/gemini_bridge.py backend/tests/test_bridges.py
git commit -m "feat(gemini-bridge): implement lifecycle methods (start/stop/send_prompt/interrupt)"
```

---

## Task 7: Manager routing — enable bridge for `gemini` agent type

**Files:**
- Modify: `backend/src/duckdome/wrapper/manager.py` (2 spots)
- Modify: `backend/tests/test_bridges.py`

**Step 7.1: Update the routing test.**

Find `TestManagerBridgeRouting.test_use_bridge_gemini_legacy` in `test_bridges.py` and rename it + flip the assertion:

```python
    def test_use_bridge_gemini(self):
        assert AgentProcessManager._use_bridge("gemini") is True

    def test_create_bridge_gemini(self, tmp_path):
        mgr = AgentProcessManager(data_dir=tmp_path)
        bridge = mgr._create_bridge("gemini", "general")
        assert isinstance(bridge, GeminiBridge)
```

Also delete the old `test_create_bridge_unknown_raises` `"gemini"` case and replace its agent type with a truly unknown one like `"nonexistent"`.

At the top of `test_bridges.py`, add `from duckdome.bridges.gemini_bridge import GeminiBridge` to the imports if not already there.

**Step 7.2: Run tests — verify failure.** Expected: both new tests fail because manager still returns False / raises for `gemini`.

**Step 7.3: Update the manager.**

In `backend/src/duckdome/wrapper/manager.py`:

```python
    @staticmethod
    def _use_bridge(agent_type: str) -> bool:
        """Return True if this agent type should use the new bridge path."""
        return agent_type in ("codex", "claude", "gemini")

    def _create_bridge(self, agent_type: str, channel_id: str) -> AgentBridge:
        if agent_type == "codex":
            return CodexBridge()
        if agent_type == "claude":
            return ClaudeBridge(receiver_port=self._app_port)
        if agent_type == "gemini":
            return GeminiBridge()
        raise ValueError(f"No bridge for agent type: {agent_type}")
```

Add `from duckdome.bridges.gemini_bridge import GeminiBridge` at the top of the file alongside the other bridge imports.

**Step 7.4: Run the full bridge test suite.**

Run: `cd backend && uv run pytest tests/test_bridges.py -v`
Expected: all new Gemini tests + all pre-existing bridge tests pass. The 5 known-broken tests live in *other* files and are unaffected.

**Step 7.5: Run the whole backend suite to catch regressions.**

Run: `cd backend && uv run pytest -q 2>&1 | tail -15`
Expected: `<same-5> failed, <381 + new>` passed. Zero new failures.

**Step 7.6: Commit.**

```bash
git add backend/src/duckdome/wrapper/manager.py backend/tests/test_bridges.py
git commit -m "feat(gemini-bridge): route gemini agents through GeminiBridge"
```

---

## Task 8: Emit-error isolation coverage for GeminiBridge

**Why:** The existing `TestEmitErrorIsolation` only tests `CodexBridge`. Add a parallel case for `GeminiBridge` to make sure listener failures don't corrupt its read loop — cheap, protective, matches project convention.

**Files:**
- Modify: `backend/tests/test_bridges.py`

**Step 8.1:** Add to `TestEmitErrorIsolation`:

```python
    def test_gemini_failing_listener_does_not_block_others(self):
        bridge = _make_gemini_bridge()
        results = []

        def bad(e): raise ValueError("boom")
        def good(e): results.append("ok")

        bridge.on(bridge.MESSAGE_DELTA, bad)
        bridge.on(bridge.MESSAGE_DELTA, good)
        bridge._handle_notification("session/update", {
            "sessionId": "s1",
            "update": {"sessionUpdate": "agent_message_chunk",
                       "content": {"type": "text", "text": "x"}},
        })
        assert results == ["ok"]
```

**Step 8.2: Run, expect pass.**

**Step 8.3: Commit.**

```bash
git add backend/tests/test_bridges.py
git commit -m "test(gemini-bridge): cover emit error isolation"
```

---

## Task 9: Verification + push

**Step 9.1: Full backend test run.**

Run: `cd backend && uv run pytest 2>&1 | tail -20`
Expected: only the 5 pre-existing baseline failures remain. No new failures.

**Step 9.2: Lint/typecheck if the project runs them.**

Run: `cd backend && uv run ruff check src/duckdome/bridges/gemini_bridge.py 2>&1` (if ruff is configured — check `pyproject.toml` first).

**Step 9.3: Manual smoke test (optional but recommended).**

Start the backend in dev mode, spawn a Gemini agent in a repo channel, send a simple prompt like "list the files in this directory", and confirm:
- Status transitions `offline → idle → working → idle`
- Agent message appears in the channel
- Any tool call (`run_shell_command`, etc.) surfaces as a tool-call event and the `requestPermission` flow produces an approval card
- Tool result appears in the channel after approval

**Step 9.4: Push the branch.** (Ask the user before pushing; don't push unprompted per the project's git safety rules.)

---

## Scope Reminders (do NOT do these in this PR)

- Do **not** delete `backend/src/duckdome/runner/gemini.py`. It remains as a fallback.
- Do **not** implement interactive auth UI. If auth fails, surface a clear `ErrorEvent` and leave the bridge offline.
- Do **not** wire Gemini into U5 inter-agent routing. That's tracked separately.
- Do **not** add fs-write approval gating. Per-design decision, fs is pass-through.
- Do **not** refactor `codex_bridge.py` to share helpers with `gemini_bridge.py`. Copy the minimal helpers. Refactor can happen later once both bridges are stable.
- Do **not** touch anything in `tests/test_mcp_bridge.py` or `tests/test_main_startup.py` — those failures are pre-existing and out of scope.

## Risks to watch while executing

1. **Wire method names.** The draft method names (`initialize`, `session/new`, `session/prompt`, `session/cancel`, `session/update`, `session/request_permission`, `fs/read_text_file`, `fs/write_text_file`) come from the ACP spec convention. Task 0 will confirm or correct them. **Do not skip Task 0.**
2. **Auth.** If the user has no `GEMINI_API_KEY` and no pre-configured OAuth state, `session/new` will return a `-32000` RequestError. That's expected behavior — the bridge surfaces it as an `ErrorEvent` and stays offline. Do not attempt to drive interactive auth.
3. **Turn boundaries.** The plan assumes `session/prompt` is a request that *awaits* turn completion. If the transcript shows it instead returning immediately and completion coming via a separate `session/update` with kind like `turn_completed`, adjust Task 6's `send_prompt` to track turn state via notifications rather than the request response.
4. **Blocking stdin writes.** `asyncio.to_thread` wraps the blocking writes — same pattern as CodexBridge. Do not introduce an async stdio transport.
