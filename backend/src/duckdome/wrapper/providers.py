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
) -> LaunchArgs:
    """Build provider-specific CLI command and env for persistent interactive mode."""
    match agent_type:
        case "claude":
            return LaunchArgs(
                cmd=[
                    "claude",
                    "--mcp-config", mcp_config_path.as_posix(),
                ],
            )
        case "codex":
            return LaunchArgs(
                cmd=[
                    "codex",
                    "--mcp-config", mcp_config_path.as_posix(),
                ],
            )
        case "gemini":
            # Gemini uses env var for MCP config
            return LaunchArgs(
                cmd=["gemini"],
                env={"GEMINI_MCP_CONFIG": mcp_config_path.as_posix()},
            )
        case _:
            raise ValueError(f"Unknown agent type: {agent_type}")
