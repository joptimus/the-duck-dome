# DEPRECATED: This module uses one-shot subprocess.run and will be removed.
# See duckdome.wrapper for the persistent process replacement.
from __future__ import annotations

from pathlib import Path

from duckdome.runner.base import BaseExecutor, RunResult
from duckdome.runner.claude import _run_cli
from duckdome.runner.context import RunContext, build_prompt


class GeminiExecutor(BaseExecutor):
    def execute(self, ctx: RunContext, timeout_s: int = 120) -> RunResult:
        """Run Gemini CLI in one-shot headless mode."""
        prompt = build_prompt(ctx)

        cwd: str | None = None
        if ctx.channel.channel_type == "repo" and ctx.channel.repo_path:
            p = Path(ctx.channel.repo_path)
            if p.is_dir():
                cwd = str(p)

        cmd = ["gemini", "--prompt", prompt]

        return _run_cli(cmd, cwd, timeout_s, "gemini")
