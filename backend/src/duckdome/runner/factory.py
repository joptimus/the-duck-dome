# DEPRECATED: This module uses one-shot subprocess.run and will be removed.
# See duckdome.wrapper for the persistent process replacement.
from __future__ import annotations

from duckdome.runner.base import BaseExecutor
from duckdome.runner.claude import ClaudeExecutor
from duckdome.runner.codex import CodexExecutor
from duckdome.runner.gemini import GeminiExecutor


def get_executor(agent_type: str) -> BaseExecutor:
    match agent_type:
        case "claude":
            return ClaudeExecutor()
        case "codex":
            return CodexExecutor()
        case "gemini":
            return GeminiExecutor()
        case _:
            raise ValueError(f"Unknown agent type: {agent_type}")
