from __future__ import annotations


DUCKDOME_STARTUP_SAFE_TOOLS: tuple[str, ...] = (
    "chat_channels",
    "chat_claim",
    "chat_join",
    "chat_read",
    "chat_rules",
    "chat_send",
    "chat_who",
)


def claude_allowed_mcp_tools(server_name: str = "duckdome") -> tuple[str, ...]:
    return tuple(
        f"mcp__{server_name}__{tool_name}"
        for tool_name in DUCKDOME_STARTUP_SAFE_TOOLS
    )
