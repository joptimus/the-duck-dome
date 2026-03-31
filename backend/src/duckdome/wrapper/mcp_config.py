from __future__ import annotations

import json
import secrets
from pathlib import Path


def generate_agent_token() -> str:
    """Generate a random bearer token for agent→MCP authentication.

    The token is included in the MCP config passed to Claude Code (and other
    agent CLIs) so that they authenticate with a static Bearer header instead
    of attempting interactive OAuth discovery.  The MCP proxy / upstream server
    does not validate this token — it is only used to suppress OAuth flows.
    """
    return secrets.token_hex(32)


def generate_mcp_config(
    config_dir: Path,
    agent_name: str,
    mcp_url: str,
    token: str = "",
) -> Path:
    """Write a per-agent MCP config JSON file for use with claude --mcp-config.

    Including a static Authorization header suppresses Claude Code's OAuth
    discovery flow, which would otherwise prompt for interactive browser auth
    when connecting to an HTTP MCP server with no /.well-known/ endpoint.
    """
    config_dir.mkdir(parents=True, exist_ok=True)
    entry: dict = {"type": "http", "url": mcp_url}
    if token:
        entry["headers"] = {"Authorization": f"Bearer {token}"}
    config = {"mcpServers": {"duckdome": entry}}
    path = config_dir / f"mcp-config-{agent_name}.json"
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path


def generate_gemini_settings(
    config_dir: Path,
    agent_name: str,
    mcp_url: str,
    token: str = "",
) -> Path:
    """Write a Gemini CLI settings JSON file with MCP config."""
    config_dir.mkdir(parents=True, exist_ok=True)
    entry: dict = {"type": "http", "httpUrl": mcp_url, "trust": True}
    if token:
        entry["headers"] = {"Authorization": f"Bearer {token}"}
    config = {
        "mcpServers": {"duckdome": entry},
        "security": {
            "folderTrust": {"enabled": True},
        },
    }
    path = config_dir / f"gemini-settings-{agent_name}.json"
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path
