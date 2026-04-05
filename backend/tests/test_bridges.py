"""Tests for the bridges package (AgentBridge, CodexBridge, ClaudeBridge, hook receiver, manager routing)."""
from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from duckdome.bridges.base import AgentBridge, AgentConfig
from duckdome.bridges.codex_bridge import CodexBridge
from duckdome.bridges.claude_bridge import ClaudeBridge
from duckdome.bridges.claude_hook_receiver import (
    register_hook_handler,
    unregister_hook_handler,
)
from duckdome.bridges.events import (
    AgentMessageEvent,
    AgentStatus,
    ApprovalRequestEvent,
    StatusChangeEvent,
    SubagentEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from duckdome.wrapper.manager import AgentProcessManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_codex_bridge() -> CodexBridge:
    bridge = CodexBridge()
    bridge._agent_id = "codex--test"
    bridge._config = AgentConfig(agent_type="codex", channel_id="general", cwd="/tmp")
    return bridge


def _make_claude_bridge() -> ClaudeBridge:
    bridge = ClaudeBridge(receiver_port=8000)
    bridge._agent_id = "claude--test"
    bridge._config = AgentConfig(agent_type="claude", channel_id="general", cwd="/tmp")
    return bridge


def _collect(bridge: AgentBridge, event_type: str) -> list:
    events: list = []
    bridge.on(event_type, lambda e: events.append(e))
    return events


# ===========================================================================
# Test: app loads with hooks router
# ===========================================================================

class TestAppHooksRouter:
    def test_hooks_route_exists(self, app):
        routes = [r.path for r in app.routes]
        assert "/hooks/claude" in routes

    def test_hooks_post_unknown_agent_returns_empty(self, client):
        resp = client.post(
            "/hooks/claude?agent=unknown",
            json={"hook_event_name": "PreToolUse", "tool_name": "Bash"},
        )
        assert resp.status_code == 200
        assert resp.json() == {}


# ===========================================================================
# Test: hook receiver routes to handler
# ===========================================================================

class TestHookReceiver:
    def test_registered_handler_receives_payload(self, client):
        received = []

        def handler(event: str, payload: dict) -> dict:
            received.append((event, payload))
            return {"decision": "approve"}

        register_hook_handler("recv-test", handler)
        try:
            resp = client.post(
                "/hooks/claude?agent=recv-test",
                json={"hook_event_name": "PreToolUse", "tool_name": "Bash"},
            )
            assert resp.status_code == 200
            assert resp.json() == {"decision": "approve"}
            assert len(received) == 1
            assert received[0][0] == "PreToolUse"
        finally:
            unregister_hook_handler("recv-test")

    def test_handler_exception_returns_empty(self, client):
        def bad_handler(event: str, payload: dict) -> dict:
            raise RuntimeError("boom")

        register_hook_handler("bad-test", bad_handler)
        try:
            resp = client.post(
                "/hooks/claude?agent=bad-test",
                json={"hook_event_name": "Stop"},
            )
            assert resp.status_code == 200
            assert resp.json() == {}
        finally:
            unregister_hook_handler("bad-test")


# ===========================================================================
# Test: CodexBridge notification dispatch
# ===========================================================================

class TestCodexBridgeNotifications:
    def test_turn_started_emits_working(self):
        bridge = _make_codex_bridge()
        events = _collect(bridge, bridge.STATUS_CHANGE)
        bridge._handle_notification("turn/started", {"turnId": "t1"})
        assert len(events) == 1
        assert events[0].status == AgentStatus.WORKING
        assert bridge._active_turn_id == "t1"

    def test_turn_completed_emits_idle(self):
        bridge = _make_codex_bridge()
        bridge._active_turn_id = "t1"
        events = _collect(bridge, bridge.STATUS_CHANGE)
        bridge._handle_notification("turn/completed", {})
        assert len(events) == 1
        assert events[0].status == AgentStatus.IDLE
        assert bridge._active_turn_id is None

    def test_item_started_emits_tool_call(self):
        bridge = _make_codex_bridge()
        events = _collect(bridge, bridge.TOOL_CALL)
        bridge._handle_notification("item/started", {
            "type": "commandExecution",
            "itemId": "item1",
            "name": "local_shell",
        })
        assert len(events) == 1
        assert events[0].tool_name == "local_shell"
        assert events[0].call_id == "item1"

    def test_item_completed_agent_message(self):
        bridge = _make_codex_bridge()
        events = _collect(bridge, bridge.MESSAGE)
        bridge._handle_notification("item/completed", {
            "type": "agentMessage",
            "itemId": "item2",
            "content": [
                {"type": "text", "text": "Hello "},
                {"type": "text", "text": "world"},
            ],
        })
        assert len(events) == 1
        assert events[0].text == "Hello \nworld"

    def test_item_completed_tool_result(self):
        bridge = _make_codex_bridge()
        events = _collect(bridge, bridge.TOOL_RESULT)
        bridge._handle_notification("item/completed", {
            "type": "localShell",
            "itemId": "item3",
            "name": "bash",
            "status": "completed",
            "output": "file.txt",
        })
        assert len(events) == 1
        assert events[0].success is True
        assert events[0].output == "file.txt"

    def test_error_notification(self):
        bridge = _make_codex_bridge()
        events = _collect(bridge, bridge.ERROR)
        bridge._handle_notification("error", {
            "message": "something broke",
            "codexErrorInfo": "details",
        })
        assert len(events) == 1
        assert events[0].error == "something broke"

    def test_subagent_spawn_begin(self):
        bridge = _make_codex_bridge()
        events = _collect(bridge, bridge.SUBAGENT)
        bridge._handle_notification("collabAgentSpawnBegin", {
            "subagentId": "sub1",
            "subagentType": "fork",
        })
        assert len(events) == 1
        assert events[0].started is True
        assert events[0].subagent_id == "sub1"

    def test_subagent_spawn_end(self):
        bridge = _make_codex_bridge()
        events = _collect(bridge, bridge.SUBAGENT)
        bridge._handle_notification("collabAgentSpawnEnd", {
            "subagentId": "sub1",
            "subagentType": "fork",
        })
        assert len(events) == 1
        assert events[0].started is False

    def test_message_delta(self):
        bridge = _make_codex_bridge()
        events = _collect(bridge, bridge.MESSAGE_DELTA)
        bridge._handle_notification("item/agentMessage/delta", {"delta": "chunk"})
        assert len(events) == 1
        assert events[0].delta == "chunk"

    def test_unhandled_notification_no_crash(self):
        bridge = _make_codex_bridge()
        bridge._handle_notification("some/unknown/thing", {})


# ===========================================================================
# Test: CodexBridge JSON-RPC message classification
# ===========================================================================

class TestCodexBridgeMessageClassification:
    def test_response_resolves_pending_future(self):
        import asyncio

        async def _run():
            bridge = _make_codex_bridge()
            fut = asyncio.get_running_loop().create_future()
            bridge._pending_requests["req-1"] = fut
            await bridge._handle_message({"id": "req-1", "result": {"ok": True}})
            assert fut.done()
            assert fut.result() == {"ok": True}

        asyncio.run(_run())

    def test_error_response_raises(self):
        import asyncio

        async def _run():
            bridge = _make_codex_bridge()
            fut = asyncio.get_running_loop().create_future()
            bridge._pending_requests["req-2"] = fut
            await bridge._handle_message({"id": "req-2", "error": {"message": "fail"}})
            assert fut.done()
            with pytest.raises(RuntimeError, match="JSON-RPC error"):
                fut.result()

        asyncio.run(_run())

    def test_notification_dispatches(self):
        import asyncio

        async def _run():
            bridge = _make_codex_bridge()
            events = _collect(bridge, bridge.STATUS_CHANGE)
            await bridge._handle_message({
                "method": "turn/started",
                "params": {"turnId": "t99"},
            })
            assert len(events) == 1

        asyncio.run(_run())


# ===========================================================================
# Test: ClaudeBridge hook handling
# ===========================================================================

class TestClaudeBridgeHooks:
    def test_send_prompt_fails_fast_when_mcp_config_path_is_missing(self, monkeypatch):
        bridge = _make_claude_bridge()
        bridge._config = AgentConfig(
            agent_type="claude",
            channel_id="general",
            cwd="/tmp",
            extra={"mcp_config_path": "/tmp/does-not-exist-mcp-config.json"},
        )
        monkeypatch.setattr("duckdome.bridges.claude_bridge.shutil.which", lambda _: "/usr/bin/claude")

        with pytest.raises(FileNotFoundError, match="Claude MCP config not found"):
            asyncio.run(bridge.send_prompt("hello", "general", "system"))

    def test_pre_tool_use_emits_tool_call(self):
        bridge = _make_claude_bridge()
        events = _collect(bridge, bridge.TOOL_CALL)
        result = bridge._handle_hook("PreToolUse", {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_use_id": "tu_1",
        })
        assert len(events) == 1
        assert events[0].tool_name == "Bash"
        assert events[0].call_id == "tu_1"
        # Default auto-approve returns empty dict
        assert result == {}

    def test_post_tool_use_emits_tool_result(self):
        bridge = _make_claude_bridge()
        events = _collect(bridge, bridge.TOOL_RESULT)
        bridge._handle_hook("PostToolUse", {
            "tool_name": "Read",
            "tool_input": {},
            "tool_response": "file contents here",
            "tool_use_id": "tu_2",
        })
        assert len(events) == 1
        assert events[0].tool_name == "Read"
        assert events[0].success is True
        assert "file contents" in events[0].output

    def test_post_tool_use_failure_emits_failed_result(self):
        bridge = _make_claude_bridge()
        events = _collect(bridge, bridge.TOOL_RESULT)
        bridge._handle_hook("PostToolUseFailure", {
            "tool_name": "Write",
            "tool_input": {},
            "tool_use_id": "tu_3",
            "error": "permission denied",
        })
        assert len(events) == 1
        assert events[0].success is False
        assert "permission denied" in events[0].output

    def test_stop_emits_idle_and_message(self):
        bridge = _make_claude_bridge()
        status_events = _collect(bridge, bridge.STATUS_CHANGE)
        msg_events = _collect(bridge, bridge.MESSAGE)
        bridge._handle_hook("Stop", {
            "last_assistant_message": "Done!",
        })
        assert len(status_events) == 1
        assert status_events[0].status == AgentStatus.IDLE
        assert len(msg_events) == 1
        assert msg_events[0].text == "Done!"

    def test_subagent_start_emits_event(self):
        bridge = _make_claude_bridge()
        events = _collect(bridge, bridge.SUBAGENT)
        bridge._handle_hook("SubagentStart", {
            "agent_id": "sub1",
            "agent_type": "general-purpose",
        })
        assert len(events) == 1
        assert events[0].started is True
        assert events[0].subagent_type == "general-purpose"

    def test_subagent_stop_emits_event(self):
        bridge = _make_claude_bridge()
        events = _collect(bridge, bridge.SUBAGENT)
        bridge._handle_hook("SubagentStop", {
            "agent_id": "sub1",
            "agent_type": "general-purpose",
            "last_assistant_message": "result",
        })
        assert len(events) == 1
        assert events[0].started is False
        assert events[0].last_message == "result"

    def test_permission_request_blocks_until_approved(self):
        bridge = _make_claude_bridge()
        events = _collect(bridge, bridge.APPROVAL_REQUEST)
        result_holder = []

        def call_hook():
            r = bridge._handle_hook("PermissionRequest", {
                "tool_name": "Bash",
                "tool_input": {"command": "rm -rf /"},
            })
            result_holder.append(r)

        t = threading.Thread(target=call_hook)
        t.start()

        # Wait for the approval to be registered
        import time
        for _ in range(50):
            if bridge._pending_approvals:
                break
            time.sleep(0.05)

        assert len(events) == 1
        approval_id = events[0].approval_id

        # Approve it (sync since we're not in async context)
        entry = bridge._pending_approvals.get(approval_id)
        assert entry is not None
        event_obj, decision = entry
        decision["decision"] = "approve"
        event_obj.set()

        t.join(timeout=5)
        assert len(result_holder) == 1
        assert result_holder[0] == {"decision": "approve"}

    def test_unhandled_hook_no_crash(self):
        bridge = _make_claude_bridge()
        result = bridge._handle_hook("SomeUnknownHook", {})
        assert result == {}


# ===========================================================================
# Test: _emit error isolation
# ===========================================================================

class TestEmitErrorIsolation:
    def test_failing_listener_does_not_block_others(self):
        bridge = _make_codex_bridge()
        results = []

        def bad(e):
            raise ValueError("boom")

        def good(e):
            results.append("ok")

        bridge.on(bridge.STATUS_CHANGE, bad)
        bridge.on(bridge.STATUS_CHANGE, good)

        bridge._emit(bridge.STATUS_CHANGE, StatusChangeEvent(
            agent_id="a", agent_type="codex", channel_id="ch",
            status=AgentStatus.IDLE,
        ))
        assert results == ["ok"]


# ===========================================================================
# Test: manager bridge routing
# ===========================================================================

class TestManagerBridgeRouting:
    def test_use_bridge_codex(self):
        assert AgentProcessManager._use_bridge("codex") is True

    def test_use_bridge_claude(self):
        assert AgentProcessManager._use_bridge("claude") is True

    def test_use_bridge_gemini_legacy(self):
        assert AgentProcessManager._use_bridge("gemini") is False

    def test_create_bridge_codex(self, tmp_path):
        mgr = AgentProcessManager(data_dir=tmp_path)
        bridge = mgr._create_bridge("codex", "general")
        assert isinstance(bridge, CodexBridge)

    def test_create_bridge_claude(self, tmp_path):
        mgr = AgentProcessManager(data_dir=tmp_path)
        bridge = mgr._create_bridge("claude", "general")
        assert isinstance(bridge, ClaudeBridge)

    def test_create_bridge_unknown_raises(self, tmp_path):
        mgr = AgentProcessManager(data_dir=tmp_path)
        with pytest.raises(ValueError, match="No bridge"):
            mgr._create_bridge("gemini", "general")

    def test_connect_bridge_events_wires_status(self, tmp_path):
        mgr = AgentProcessManager(data_dir=tmp_path)
        ws = MagicMock()
        mgr._ws_manager = ws

        bridge = CodexBridge()
        mgr._connect_bridge_events(bridge, "codex--test")

        bridge._emit(bridge.STATUS_CHANGE, StatusChangeEvent(
            agent_id="codex--test",
            agent_type="codex",
            channel_id="general",
            status=AgentStatus.WORKING,
        ))

        ws.broadcast_sync.assert_called_once()
        call_args = ws.broadcast_sync.call_args[0][0]
        assert call_args["type"] == "agent_status_change"
        assert call_args["status"] == "working"

    def test_sync_manager_routes_bridge_calls_through_dedicated_loop(self, tmp_path, monkeypatch):
        class _FakeBridge(AgentBridge):
            def __init__(self):
                super().__init__()
                self.started = False
                self.stopped = False
                self.sent_prompts = []
                self.loop_ids = {}

            async def start(self, agent_id: str, config: AgentConfig) -> None:
                self.started = True
                self.loop_ids["start"] = id(asyncio.get_running_loop())

            async def stop(self) -> None:
                self.stopped = True
                self.loop_ids["stop"] = id(asyncio.get_running_loop())

            async def send_prompt(self, text: str, channel_id: str, sender: str) -> None:
                self.sent_prompts.append((text, channel_id, sender))
                self.loop_ids["send_prompt"] = id(asyncio.get_running_loop())

            async def interrupt(self) -> None:
                return None

            async def approve(self, approval_id: str) -> None:
                self.loop_ids["approve"] = id(asyncio.get_running_loop())

            async def deny(self, approval_id: str, reason: str) -> None:
                self.loop_ids["deny"] = id(asyncio.get_running_loop())

            async def get_status(self) -> AgentStatus:
                return AgentStatus.IDLE

        mgr = AgentProcessManager(data_dir=tmp_path)
        fake_bridge = _FakeBridge()
        monkeypatch.setattr(mgr, "_create_bridge", lambda agent_type, channel_id: fake_bridge)

        try:
            assert mgr.start_agent("codex", cwd=str(tmp_path), channel_id="room-1") is True
            assert mgr.trigger_agent("codex", "human", "inspect this", "room-1") is True
            assert mgr.stop_agent("codex", "room-1") is True
        finally:
            mgr.stop_all()

        assert fake_bridge.started is True
        assert fake_bridge.stopped is True
        # 2 prompts: startup prompt (sent at bridge start) + trigger prompt
        assert len(fake_bridge.sent_prompts) == 2
        startup_text, _startup_channel, startup_sender = fake_bridge.sent_prompts[0]
        assert "#room-1" in startup_text
        assert startup_sender == "system"
        trigger_text = fake_bridge.sent_prompts[1][0]
        assert "you were mentioned" in trigger_text
        assert fake_bridge.loop_ids["start"] == fake_bridge.loop_ids["send_prompt"]
        assert fake_bridge.loop_ids["start"] == fake_bridge.loop_ids["stop"]


# ===========================================================================
# Test: GeminiBridge construction
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

    def test_notification_dispatches_to_handler(self):
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

    def test_server_request_routes_to_handler(self):
        async def _run():
            bridge = _make_gemini_bridge()
            calls = []
            async def capture(msg):
                calls.append(msg)
            bridge._handle_server_request = capture  # type: ignore
            await bridge._handle_message({
                "jsonrpc": "2.0",
                "id": "srv-1",
                "method": "fs/read_text_file",
                "params": {"path": "/tmp/x"},
            })
            assert len(calls) == 1
            assert calls[0]["method"] == "fs/read_text_file"
        asyncio.run(_run())

    def test_fail_pending_futures_rejects_all(self):
        async def _run():
            bridge = _make_gemini_bridge()
            loop = asyncio.get_running_loop()
            req_fut = loop.create_future()
            app_fut = loop.create_future()
            bridge._pending_requests["r1"] = req_fut
            bridge._pending_approvals["a1"] = app_fut
            bridge._fail_pending_futures("stopping")
            assert bridge._pending_requests == {}
            assert bridge._pending_approvals == {}
            assert req_fut.done() and app_fut.done()
            with pytest.raises(RuntimeError, match="stopping"):
                req_fut.result()
            with pytest.raises(RuntimeError, match="stopping"):
                app_fut.result()
        asyncio.run(_run())
