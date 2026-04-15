"""Generate per-agent settings.local.json for Claude Code HTTP hooks.

Writes a temporary settings file that configures Claude Code to POST all
hook events to DuckDome's hook receiver endpoint.
"""
from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from duckdome.wrapper.safe_tools import claude_allowed_mcp_tools

logger = logging.getLogger(__name__)


def generate_claude_hook_settings(
    *,
    agent_id: str,
    receiver_port: int,
    receiver_host: str = "127.0.0.1",
    output_dir: Path | None = None,
) -> Path:
    """Write a settings.local.json with HTTP hooks and return its path.

    Sync hooks (PreToolUse, PermissionRequest) block the agent until
    DuckDome responds with an approve/block decision.  All other hooks
    run async so they don't slow down the agent.
    """
    base_url = f"http://{receiver_host}:{receiver_port}/hooks/claude?agent={agent_id}"

    def _hook(*, is_async: bool = False) -> list[dict]:
        hook: dict = {"type": "http", "url": base_url}
        if is_async:
            hook["async"] = True
        return [{"hooks": [hook]}]

    # Tools that are safe-by-default and should not require per-call approval.
    # Without this allowlist every Claude turn triggers PermissionRequest for
    # TodoWrite / Read / Grep / the DuckDome MCP chat tools — and since
    # chat_send is how Claude replies in a channel, Claude cannot respond at
    # all unless the user clicks approve on every single message.
    # Dangerous tools (Bash, Edit, Write, WebFetch, …) are intentionally NOT
    # listed here and still go through the approval flow.
    safe_tools = [
        # Claude Code built-ins that are read-only or sandbox-safe
        "TodoWrite",
        "Read",
        "Grep",
        "Glob",
        "LS",
        # DuckDome MCP tools — derived from safe_tools.py so this list
        # stays in sync with the PreToolUse hook handler and providers.py.
        *claude_allowed_mcp_tools(),
    ]

    settings = {
        "permissions": {
            "allow": safe_tools,
            "ask": [],
            "deny": [],
        },
        "hooks": {
            # Sync — DuckDome can approve/block/modify
            "PreToolUse": _hook(),
            "PermissionRequest": _hook(),
            # Async — observation only
            "PostToolUse": _hook(is_async=True),
            "PostToolUseFailure": _hook(is_async=True),
            "SubagentStart": _hook(is_async=True),
            "SubagentStop": _hook(is_async=True),
            "Stop": _hook(is_async=True),
            "Notification": _hook(is_async=True),
            "TaskCreated": _hook(is_async=True),
            "TaskCompleted": _hook(is_async=True),
            "SessionStart": _hook(is_async=True),
        },
    }

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="duckdome-claude-"))

    output_dir.mkdir(parents=True, exist_ok=True)
    settings_path = output_dir / "settings.local.json"
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    logger.info("Wrote Claude hook settings for agent %s: %s", agent_id, settings_path)
    return settings_path
