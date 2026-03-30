from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LaunchArgs:
    cmd: list[str]
    env: dict[str, str] = field(default_factory=dict)


def build_launch_args(
    agent_type: str,
    mcp_config_path: Path,
    cwd: str | None,
    mcp_url: str = "",
    auto_approve: bool = True,
) -> LaunchArgs:
    """Build provider-specific CLI command and env for persistent interactive mode."""
    match agent_type:
        case "claude":
            cmd = [
                "claude",
                "--mcp-config", mcp_config_path.as_posix(),
            ]
            if auto_approve:
                cmd.append("--dangerously-skip-permissions")
            return LaunchArgs(cmd=cmd)
        case "codex":
            cmd = [
                "codex",
                "-c", f'mcp_servers.duckdome.url="{mcp_url}"',
            ]
            if auto_approve:
                cmd.append("--dangerously-bypass-approvals-and-sandbox")
            return LaunchArgs(cmd=cmd)
        case "gemini":
            cmd = ["gemini"]
            if auto_approve:
                cmd.append("--yolo")
            return LaunchArgs(
                cmd=cmd,
                env={"GEMINI_CLI_SYSTEM_SETTINGS_PATH": mcp_config_path.as_posix()},
            )
        case _:
            raise ValueError(f"Unknown agent type: {agent_type}")
