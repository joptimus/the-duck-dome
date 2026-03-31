from threading import Thread

from duckdome.wrapper.manager import (
    AgentProcess,
    AgentProcessManager,
    _build_trigger_prompt,
    _resolve_inject_delay,
    _should_use_proxy,
)


def test_build_trigger_prompt_includes_trigger_context():
    prompt = _build_trigger_prompt(
        agent_type="codex",
        channel="ch-123",
        sender="human",
        text="Please inspect the failing test and patch it.",
    )

    assert 'chat_join tool with channel="ch-123"' in prompt
    assert 'agent_type="codex"' in prompt
    assert "You were triggered by human." in prompt
    assert "Requested work: Please inspect the failing test and patch it." in prompt


def test_build_trigger_prompt_tells_agent_to_do_work_before_reply():
    prompt = _build_trigger_prompt(
        agent_type="codex",
        channel="general",
        sender="claude",
        text="Run the formatter and fix the lints.",
    )

    assert "Complete the requested work before replying." in prompt
    assert "If the task requires tools, use them." in prompt
    assert "send it with chat_send" in prompt


def test_build_trigger_prompt_uses_claude_specific_mcp_wording():
    prompt = _build_trigger_prompt(
        agent_type="claude",
        channel="ch-123",
        sender="user",
        text="@claude hi",
    )

    assert 'DuckDome MCP is already configured in this session under the server name "duckdome".' in prompt
    assert 'Use the DuckDome MCP chat tools for this task.' in prompt
    assert 'Join channel "ch-123", read the latest messages there' in prompt
    assert 'Do not treat this as a generic MCP resource lookup.' in prompt
    assert 'Do not inspect ~/.claude settings, .mcp.json files' in prompt
    assert 'Do not use curl or direct HTTP calls for DuckDome chat' in prompt
    assert 'Request: @claude hi' in prompt
    assert 'You were triggered by user.' in prompt
    assert 'Reply in chat when done.' in prompt


class _FakeProxy:
    def __init__(self, channel: str):
        self._channel = channel

    def _get_joined_channel(self) -> str:
        return self._channel


def test_claude_uses_direct_mcp_like_legacy_wrapper():
    assert _should_use_proxy("claude") is False
    assert _should_use_proxy("codex") is True
    assert _should_use_proxy("gemini") is True


def test_codex_uses_slower_inject_delay():
    assert _resolve_inject_delay("codex") == 0.3
    assert _resolve_inject_delay("claude") == 0.01


def test_post_agent_heartbeat_uses_joined_channel(tmp_path, monkeypatch):
    manager = AgentProcessManager(data_dir=tmp_path, app_port=8123)
    captured = {}

    class _FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_urlopen(request, timeout=5):
        captured["url"] = request.full_url
        captured["body"] = request.data
        return _FakeResponse()

    monkeypatch.setattr("duckdome.wrapper.manager.urlopen", _fake_urlopen)

    agent = AgentProcess(agent_type="claude", proxy=_FakeProxy("ch-123"))
    assert manager._post_agent_heartbeat(agent) is True
    assert captured["url"] == "http://127.0.0.1:8123/api/agents/heartbeat"
    assert captured["body"] == b'{"channel_id": "ch-123", "agent_type": "claude"}'


def test_post_agent_heartbeat_skips_before_channel_join(tmp_path):
    manager = AgentProcessManager(data_dir=tmp_path, app_port=9999)
    agent = AgentProcess(agent_type="claude", proxy=_FakeProxy("general"))

    assert manager._post_agent_heartbeat(agent) is False


def test_post_agent_heartbeat_falls_back_to_active_channel_without_proxy(tmp_path, monkeypatch):
    manager = AgentProcessManager(data_dir=tmp_path, app_port=8123)
    captured = {}

    class _FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_urlopen(request, timeout=5):
        captured["body"] = request.data
        return _FakeResponse()

    monkeypatch.setattr("duckdome.wrapper.manager.urlopen", _fake_urlopen)

    agent = AgentProcess(agent_type="claude", active_channel="ch-456")
    assert manager._post_agent_heartbeat(agent) is True
    assert captured["body"] == b'{"channel_id": "ch-456", "agent_type": "claude"}'


def test_queue_monitor_restarts_dead_queue_watcher(tmp_path):
    manager = AgentProcessManager(data_dir=tmp_path)
    agent = AgentProcess(agent_type="claude")
    agent.ready_event.set()
    agent.queue_thread = Thread(target=lambda: None)

    calls = []

    def _restart(_: AgentProcess) -> None:
        calls.append("restart")
        agent.stop_event.set()

    manager._start_queue_watcher_thread = _restart  # type: ignore[method-assign]
    manager._is_alive = lambda _: True  # type: ignore[method-assign]

    original_interval = __import__("duckdome.wrapper.manager", fromlist=["QUEUE_MONITOR_INTERVAL"])
    old_value = original_interval.QUEUE_MONITOR_INTERVAL
    original_interval.QUEUE_MONITOR_INTERVAL = 0.01
    try:
        manager._queue_monitor_loop(agent)
    finally:
        original_interval.QUEUE_MONITOR_INTERVAL = old_value

    assert calls == ["restart"]
