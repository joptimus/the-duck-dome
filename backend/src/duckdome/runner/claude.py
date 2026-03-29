from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from duckdome.runner.context import RunContext, build_prompt


@dataclass
class RunResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int


def execute(ctx: RunContext, timeout_s: int = 120) -> RunResult:
    """Run Claude CLI in one-shot headless mode.

    For repo channels, cwd is set to the repo_path.
    For general channels, cwd is the system default.
    """
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

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
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
            stderr=f"Claude CLI timed out after {timeout_s}s",
            exit_code=-1,
            duration_ms=duration_ms,
        )
    except FileNotFoundError:
        duration_ms = int((time.time() - start) * 1000)
        return RunResult(
            stdout="",
            stderr="claude CLI not found in PATH",
            exit_code=-2,
            duration_ms=duration_ms,
        )
