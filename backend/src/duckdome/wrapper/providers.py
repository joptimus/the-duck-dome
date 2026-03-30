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
) -> LaunchArgs:
    """Build provider-specific CLI command and env for persistent interactive mode."""
    match agent_type:
        case "claude":
            return LaunchArgs(
                cmd=[
                    "claude",
                    "--mcp-config", str(mcp_config_path),
                ],
            )
        case "codex":
            return LaunchArgs(
                cmd=[
                    "codex",
                    "-c", f'mcp_servers.duckdome.url="{mcp_url}"',
                ],
            )
        case "gemini":
            return LaunchArgs(
                cmd=["gemini"],
                env={"GEMINI_CLI_SYSTEM_SETTINGS_PATH": str(mcp_config_path)},
            )
        case _:
            raise ValueError(f"Unknown agent type: {agent_type}")
