from __future__ import annotations

from types import SimpleNamespace

from duckdome.wrapper import injector


def test_inject_via_tmux_targets_primary_pane_for_text_and_enter(monkeypatch):
    calls: list[list[str]] = []

    def _fake_run(cmd, capture_output=True):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(injector.subprocess, "run", _fake_run)
    monkeypatch.setattr(injector.time, "sleep", lambda *_: None)

    ok = injector._inject_via_tmux("hello", "duckdome-claude", delay=0.0)

    assert ok is True
    assert calls == [
        ["tmux", "send-keys", "-t", "duckdome-claude:0.0", "-l", "hello"],
        ["tmux", "send-keys", "-t", "duckdome-claude:0.0", "Enter"],
    ]


def test_inject_via_tmux_returns_false_when_enter_fails(monkeypatch):
    call_count = {"n": 0}

    def _fake_run(cmd, capture_output=True):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return SimpleNamespace(returncode=0, stderr=b"")
        return SimpleNamespace(returncode=1, stderr=b"enter failed")

    monkeypatch.setattr(injector.subprocess, "run", _fake_run)
    monkeypatch.setattr(injector.time, "sleep", lambda *_: None)

    ok = injector._inject_via_tmux("hello", "duckdome-claude", delay=0.0)

    assert ok is False
