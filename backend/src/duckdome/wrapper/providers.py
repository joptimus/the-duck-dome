from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from duckdome.wrapper.safe_tools import (
    DUCKDOME_STARTUP_SAFE_TOOLS,
    claude_allowed_mcp_tools,
)


@dataclass
class LaunchArgs:
    cmd: list[str]
    env: dict[str, str] = field(default_factory=dict)


def build_launch_args(
    agent_type: str,
    mcp_config_path: Path,
    cwd: str | None,
    mcp_url: str = "",
) -> LaunchArgs:
    """Build provider-specific CLI command and env for persistent interactive mode."""
    match agent_type:
        case "claude":
            return LaunchArgs(
                cmd=[
                    "claude",
                    "--mcp-config", str(mcp_config_path),
                    "--strict-mcp-config",
                    "--allowedTools", *claude_allowed_mcp_tools(),
                ],
            )
        case "codex":
            cmd = [
                "codex",
                "-c", f'mcp_servers.duckdome.url="{mcp_url}"',
            ]
            for tool_name in DUCKDOME_STARTUP_SAFE_TOOLS:
                cmd.extend(
                    [
                        "-c",
                        f'mcp_servers.duckdome.tools.{tool_name}.approval_mode="never"',
                    ]
                )
            return LaunchArgs(
                cmd=cmd,
            )
        case "gemini":
            return LaunchArgs(
                cmd=["gemini"],
                env={"GEMINI_CLI_SYSTEM_SETTINGS_PATH": str(mcp_config_path)},
            )
        case _:
            raise ValueError(f"Unknown agent type: {agent_type}")
