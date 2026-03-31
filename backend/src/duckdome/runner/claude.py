# DEPRECATED: This module uses one-shot subprocess.run and will be removed.
# See duckdome.wrapper for the persistent process replacement.
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

from duckdome.runner.base import BaseExecutor, RunResult
from duckdome.runner.context import RunContext, build_system_context, build_user_message


class ClaudeExecutor(BaseExecutor):
    def execute(self, ctx: RunContext, timeout_s: int = 120) -> RunResult:
        """Run Claude CLI in one-shot headless mode."""
        system_ctx = build_system_context(ctx)
        user_msg = build_user_message(ctx)

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
            "--append-system-prompt", system_ctx,
        ]

        return _run_cli(cmd, cwd, timeout_s, "claude", stdin_text=user_msg)


def _run_cli(
    cmd: list[str],
    cwd: str | None,
    timeout_s: int,
    name: str,
    stdin_text: str | None = None,
) -> RunResult:
    # On Windows, .cmd shims (npm global installs) need shell=True.
    # Native .exe files work without it.
    use_shell = False
    if sys.platform == "win32":
        resolved = shutil.which(cmd[0])
        use_shell = resolved is not None and resolved.lower().endswith(".cmd")
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            input=stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            cwd=cwd,
            shell=use_shell,
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
