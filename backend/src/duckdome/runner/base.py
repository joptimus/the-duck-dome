# DEPRECATED: This module uses one-shot subprocess.run and will be removed.
# See duckdome.wrapper for the persistent process replacement.
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from duckdome.runner.context import RunContext


@dataclass
class RunResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int


class BaseExecutor(ABC):
    @abstractmethod
    def execute(self, ctx: RunContext, timeout_s: int = 120) -> RunResult: ...
