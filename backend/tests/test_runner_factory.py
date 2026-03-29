import pytest

from duckdome.runner.factory import get_executor
from duckdome.runner.claude import ClaudeExecutor
from duckdome.runner.codex import CodexExecutor
from duckdome.runner.gemini import GeminiExecutor


def test_get_claude_executor():
    executor = get_executor("claude")
    assert isinstance(executor, ClaudeExecutor)


def test_get_codex_executor():
    executor = get_executor("codex")
    assert isinstance(executor, CodexExecutor)


def test_get_gemini_executor():
    executor = get_executor("gemini")
    assert isinstance(executor, GeminiExecutor)


def test_unknown_agent_type_raises():
    with pytest.raises(ValueError, match="Unknown agent type"):
        get_executor("unknown-agent")


def test_each_executor_has_execute_method():
    for agent_type in ("claude", "codex", "gemini"):
        executor = get_executor(agent_type)
        assert callable(getattr(executor, "execute", None))
