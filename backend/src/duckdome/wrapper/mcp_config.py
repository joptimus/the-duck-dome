from __future__ import annotations

import json
from pathlib import Path


def generate_mcp_config(
    config_dir: Path,
    agent_name: str,
    mcp_url: str,
) -> Path:
    """Write a per-agent MCP config JSON file for use with claude --mcp-config."""
    config_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "mcpServers": {
            "duckdome": {
                "type": "http",
                "url": mcp_url,
            }
        }
    }
    path = config_dir / f"mcp-config-{agent_name}.json"
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path


def generate_gemini_settings(
    config_dir: Path,
    agent_name: str,
    mcp_url: str,
) -> Path:
    """Write a Gemini CLI settings JSON file with MCP config."""
    config_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "mcpServers": {
            "duckdome": {
                "type": "http",
                "httpUrl": mcp_url,
                "trust": True,
            }
        },
        "security": {
            "folderTrust": {"enabled": True},
        },
    }
    path = config_dir / f"gemini-settings-{agent_name}.json"
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path
