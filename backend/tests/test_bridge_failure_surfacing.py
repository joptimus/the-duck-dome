"""Bridge coroutine failures must be surfaced, not silently swallowed.

Covers review finding 2-C2: ``_submit_bridge_coro(bridge.send_prompt(...))``
futures were never inspected, so a failed prompt delivery vanished with no
log, no system message, and no WebSocket event.
"""

import time

import pytest

from duckdome.wrapper.manager import AgentProcessManager


class _FakeMessageService:
    def __init__(self):
        self.events = []

    def post_system_event(self, *, channel, subtype, agent, text):
        self.events.append(
            {"channel": channel, "subtype": subtype, "agent": agent, "text": text}
        )


class _FakeWsManager:
    def __init__(self):
        self.broadcasts = []

    def broadcast_sync(self, payload):
        self.broadcasts.append(payload)


class _FailingBridge:
    async def send_prompt(self, prompt, channel, sender):
        raise RuntimeError("turn/start timed out")


@pytest.fixture
def manager(tmp_path):
    svc = _FakeMessageService()
    ws = _FakeWsManager()
    mgr = AgentProcessManager(
        data_dir=tmp_path, message_service=svc, ws_manager=ws
    )
    yield mgr, svc, ws
    mgr._shutdown_bridge_loop()


def _wait_for(condition, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


def test_submitted_coro_failure_posts_system_error(manager):
    mgr, svc, ws = manager

    async def _boom():
        raise RuntimeError("boom")

    mgr._submit_bridge_coro(
        _boom(), description="deliver message", agent_type="claude", channel="general"
    )

    assert _wait_for(lambda: svc.events), "no system event posted for failed coro"
    event = svc.events[0]
    assert event["channel"] == "general"
    assert event["subtype"] == "error"
    assert event["agent"] == "claude"
    assert "deliver message" in event["text"]
    assert "boom" in event["text"]

    assert _wait_for(lambda: ws.broadcasts), "no agent_error broadcast for failed coro"
    broadcast = ws.broadcasts[0]
    assert broadcast["type"] == "agent_error"
    assert broadcast["channel_id"] == "general"
    assert broadcast["agent_type"] == "claude"


def test_submitted_coro_success_posts_nothing(manager):
    mgr, svc, ws = manager
    done = []

    async def _ok():
        done.append(True)

    mgr._submit_bridge_coro(
        _ok(), description="deliver message", agent_type="claude", channel="general"
    )

    assert _wait_for(lambda: done)
    time.sleep(0.05)  # give a wrongly-attached callback time to fire
    assert svc.events == []
    assert ws.broadcasts == []


def test_trigger_agent_surfaces_send_prompt_failure(manager):
    """A user @mention whose delivery fails must produce a visible error in
    the channel instead of disappearing."""
    mgr, svc, ws = manager
    with mgr._lock:
        mgr._bridges["claude--general"] = _FailingBridge()

    assert mgr.trigger_agent("claude", sender="alice", text="hello?", channel="general")

    assert _wait_for(lambda: svc.events), "send_prompt failure was swallowed"
    event = svc.events[0]
    assert event["channel"] == "general"
    assert event["subtype"] == "error"
    assert "turn/start timed out" in event["text"]
