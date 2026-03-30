from __future__ import annotations

import subprocess
import time
from pathlib import Path

from duckdome.runner.base import BaseExecutor, RunResult
from duckdome.runner.context import RunContext, build_prompt


class ClaudeExecutor(BaseExecutor):
    def execute(self, ctx: RunContext, timeout_s: int = 120) -> RunResult:
        """Run Claude CLI in one-shot headless mode."""
        prompt = build_prompt(ctx)

        cwd: str | None = None
        if ctx.channel.channel_type == "repo" and ctx.channel.repo_path:
            p = Path(ctx.channel.repo_path)
            if p.is_dir():
                cwd = str(p)

        cmd = [
            "claude",
            "--print",
            "--output-format", "text",
            "--no-session-persistence",
            "--verbose",
            prompt,
        ]

        return _run_cli(cmd, cwd, timeout_s, "claude")


def _run_cli(cmd: list[str], cwd: str | None, timeout_s: int, name: str) -> RunResult:
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            cwd=cwd,
        )
        duration_ms = int((time.time() - start) * 1000)
        return RunResult(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
            duration_ms=duration_ms,
        )
    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - start) * 1000)
        return RunResult(
            stdout="",
            stderr=f"{name} CLI timed out after {timeout_s}s",
            exit_code=-1,
            duration_ms=duration_ms,
        )
    except FileNotFoundError:
        duration_ms = int((time.time() - start) * 1000)
        return RunResult(
            stdout="",
            stderr=f"{name} CLI not found in PATH",
            exit_code=-2,
            duration_ms=duration_ms,
        )


# Backward-compatible module-level function
def execute(ctx: RunContext, timeout_s: int = 120) -> RunResult:
    return ClaudeExecutor().execute(ctx, timeout_s)
