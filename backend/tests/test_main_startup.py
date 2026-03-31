import pytest
from threading import Event

pytest.importorskip("mcp.server.fastmcp")

from duckdome.main import _start_agents_deferred


class _WrapperServiceStub:
    def __init__(self):
        self.started: list[str] = []

    def start_agent(self, agent_type: str) -> None:
        self.started.append(agent_type)


def test_start_agents_deferred_skips_launch_when_mcp_not_ready(monkeypatch):
    wrapper = _WrapperServiceStub()

    monkeypatch.setattr("duckdome.main._wait_for_mcp", lambda port=8200: False)
    monkeypatch.setattr("duckdome.main._wait_for_http", lambda port=8000: True)
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/fake")

    _start_agents_deferred(wrapper, Event())

    assert wrapper.started == []


def test_start_agents_deferred_skips_launch_when_http_not_ready(monkeypatch):
    wrapper = _WrapperServiceStub()

    monkeypatch.setattr("duckdome.main._wait_for_mcp", lambda port=8200: True)
    monkeypatch.setattr("duckdome.main._wait_for_http", lambda port=8000: False)
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/fake")

    _start_agents_deferred(wrapper, Event())

    assert wrapper.started == []


def test_start_agents_deferred_starts_available_agents(monkeypatch):
    wrapper = _WrapperServiceStub()

    monkeypatch.setattr("duckdome.main._wait_for_mcp", lambda port=8200: True)
    monkeypatch.setattr("duckdome.main._wait_for_http", lambda port=8000: True)
    monkeypatch.setattr(
        "shutil.which",
        lambda agent: "/usr/bin/fake" if agent in {"claude", "gemini"} else None,
    )

    _start_agents_deferred(wrapper, Event())

    assert wrapper.started == ["claude", "gemini"]


def test_wait_for_http_uses_health_route(monkeypatch):
    from duckdome.main import _wait_for_http

    captured = {}

    class _FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_urlopen(request, timeout=3):
        captured["url"] = request.full_url
        return _FakeResponse()

    monkeypatch.setattr("duckdome.main.urlopen", _fake_urlopen)

    assert _wait_for_http(port=8123, timeout=0.1) is True
    assert captured["url"] == "http://127.0.0.1:8123/health"
