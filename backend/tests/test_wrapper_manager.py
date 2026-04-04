from threading import Thread

from duckdome.wrapper.manager import (
    AgentProcess,
    AgentProcessManager,
    _build_startup_prompt,
    _build_trigger_prompt,
    _resolve_inject_delay,
    _should_use_proxy,
)


def test_build_trigger_prompt_is_minimal():
    prompt = _build_trigger_prompt(
        agent_type="codex",
        channel="ch-123",
        sender="human",
        text="Please inspect the failing test and patch it.",
    )
    assert "you were mentioned, take appropriate action" in prompt
    # channel/join instructions now live in the startup prompt, not here
    assert "chat_join" not in prompt


def test_build_trigger_prompt_same_for_all_agents():
    claude_prompt = _build_trigger_prompt(
        agent_type="claude", channel="general", sender="human", text="hi"
    )
    codex_prompt = _build_trigger_prompt(
        agent_type="codex", channel="general", sender="human", text="hi"
    )
    assert claude_prompt == codex_prompt


def test_build_startup_prompt_includes_channel_and_identity():
    prompt = _build_startup_prompt(agent_type="claude", channel="general")
    assert "claude" in prompt
    assert "#general" in prompt
    assert "chat_read" in prompt
    assert "chat_send" in prompt
    assert 'sender="claude"' in prompt


def test_build_startup_prompt_codex():
    prompt = _build_startup_prompt(agent_type="codex", channel="backend")
    assert "codex" in prompt
    assert "#backend" in prompt
    assert 'sender="codex"' in prompt


class _FakeProxy:
    def __init__(self, channel: str, has_joined: bool = True):
        self._channel = channel
        self._has_joined = has_joined

    def _get_joined_channel(self) -> str:
        return self._channel

    def _has_joined_channel(self) -> bool:
        return self._has_joined


def test_claude_uses_direct_mcp_like_legacy_wrapper():
    assert _should_use_proxy("claude") is False
    assert _should_use_proxy("codex") is True
    assert _should_use_proxy("gemini") is True


def test_codex_uses_slower_inject_delay():
    assert _resolve_inject_delay("codex") == 1.5
    assert _resolve_inject_delay("claude") == 0.05


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


def test_deregister_agent_presence_uses_joined_proxy_channel(tmp_path, monkeypatch):
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

    agent = AgentProcess(agent_type="codex", proxy=_FakeProxy("general", has_joined=True))
    assert manager._deregister_agent_presence(agent) is True
    assert captured["url"] == "http://127.0.0.1:8123/api/agents/deregister"
    assert captured["body"] == b'{"channel_id": "general", "agent_type": "codex"}'


def test_default_show_windows_is_false(tmp_path):
    from duckdome.wrapper.manager import AgentProcessManager
    mgr = AgentProcessManager(data_dir=tmp_path)
    assert mgr._show_windows is False


def test_set_show_windows_updates_flag(tmp_path):
    from duckdome.wrapper.manager import AgentProcessManager
    mgr = AgentProcessManager(data_dir=tmp_path)
    mgr.set_show_windows(True)
    assert mgr._show_windows is True


def test_set_show_windows_calls_open_terminal_for_tmux_agents(tmp_path):
    from unittest.mock import patch, MagicMock
    from duckdome.wrapper.manager import AgentProcessManager, AgentProcess

    mgr = AgentProcessManager(data_dir=tmp_path)
    ap = AgentProcess(agent_type="claude", tmux_session="duckdome-claude")
    ap.started_at = 1.0
    with mgr._lock:
        mgr._agents["claude"] = ap

    with patch("duckdome.wrapper.manager._open_agent_terminal") as mock_open, \
         patch("duckdome.wrapper.manager._close_agent_terminal") as mock_close, \
         patch.object(mgr, "_is_alive", return_value=True):
        mgr.set_show_windows(True)
        mock_open.assert_called_once_with("duckdome-claude")
        mock_close.assert_not_called()

        mgr.set_show_windows(False)
        mock_close.assert_called_once_with("duckdome-claude")
