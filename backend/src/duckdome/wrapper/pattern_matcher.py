"""Permission prompt pattern matching per agent type."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptMatch:
    tool: str
    description: str
    approve_key: str
    deny_key: str
    fingerprint: str


def _fingerprint(tool: str, description: str) -> str:
    raw = f"{tool}:{description}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# Claude Code patterns.
# Example prompt:
#   ❯ Do you want to allow Claude to use Bash?
#     Command: git status
#     (Y)es | (N)o | Yes, and don't ask again for this tool
_CLAUDE_TOOL_RE = re.compile(
    r"allow Claude to use (\w+)\?",
    re.IGNORECASE,
)

# Description lines appear between the tool line and the (Y)es|(N)o line.
# Common prefixes: "Command:", "File:", or just indented text.
_CLAUDE_DESC_RE = re.compile(
    r"^\s+(?:Command|File|Path|Description):\s*(.+)",
    re.MULTILINE,
)

_CLAUDE_YN_RE = re.compile(r"\(Y\)es\s*\|\s*\(N\)o", re.IGNORECASE)


def _match_claude(text: str) -> PromptMatch | None:
    tool_m = _CLAUDE_TOOL_RE.search(text)
    if not tool_m:
        return None

    yn_m = _CLAUDE_YN_RE.search(text)
    if not yn_m:
        return None

    tool = tool_m.group(1)

    desc_m = _CLAUDE_DESC_RE.search(text)
    description = desc_m.group(1).strip() if desc_m else ""

    return PromptMatch(
        tool=tool,
        description=description,
        approve_key="y",
        deny_key="n",
        fingerprint=_fingerprint(tool, description),
    )


_MATCHERS: dict[str, callable] = {
    "claude": _match_claude,
}


def match_permission_prompt(text: str, agent_type: str) -> PromptMatch | None:
    """Match a permission prompt in *text* for the given *agent_type*.

    Returns a PromptMatch if found, None otherwise.
    """
    matcher = _MATCHERS.get(agent_type)
    if matcher is None:
        return None
    return matcher(text)
