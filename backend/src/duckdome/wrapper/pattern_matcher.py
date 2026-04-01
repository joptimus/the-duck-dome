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


# Claude Code permission prompt format (as seen in the console buffer):
#
#  Bash command
#    ls /c/Users/James/Downloads 2>&1 | head -20
#    List Downloads folder contents
#  Do you want to proceed?
#  ❯ 1. Yes
#    2. Yes, allow reading from Downloads\ from this project
#    3. No
#
# Also handles the older format:
#  ❯ Do you want to allow Claude to use Bash?
#    Command: git status
#    (Y)es | (N)o | ...

# New format: "Do you want to proceed?" with numbered choices
_CLAUDE_PROCEED_RE = re.compile(
    r"Do you want to proceed\?",
    re.IGNORECASE,
)

# Tool name header line (e.g., "Bash command", "Read file", "Edit file")
_CLAUDE_TOOL_HEADER_RE = re.compile(
    r"^\s*(Bash|Read|Edit|Write|Glob|Grep|Agent|WebFetch|WebSearch|Bash command)\b",
    re.MULTILINE,
)

# Description: indented lines between tool header and "Do you want to proceed?"
# Grab the first indented line after the tool header as the description.
_CLAUDE_INDENTED_RE = re.compile(
    r"^\s{3,}(\S.+)",
    re.MULTILINE,
)

# Numbered choices: "1. Yes" means approve, "3. No" or last number means deny
_CLAUDE_YES_CHOICE_RE = re.compile(r"(\d+)\.\s*Yes\b")
_CLAUDE_NO_CHOICE_RE = re.compile(r"(\d+)\.\s*No\b")

# Old format: "(Y)es | (N)o"
_CLAUDE_YN_RE = re.compile(r"\(Y\)es\s*\|\s*\(N\)o", re.IGNORECASE)

# Old format tool name
_CLAUDE_TOOL_OLD_RE = re.compile(
    r"allow Claude to use (\w+)\?",
    re.IGNORECASE,
)

# Old format description
_CLAUDE_DESC_OLD_RE = re.compile(
    r"^\s+(?:Command|File|Path|Description):\s*(.+)",
    re.MULTILINE,
)


def _match_claude(text: str) -> PromptMatch | None:
    # Try new format first: "Do you want to proceed?" with numbered choices
    proceed_m = _CLAUDE_PROCEED_RE.search(text)
    if proceed_m:
        # Find tool name from header
        tool = "Unknown"
        tool_m = _CLAUDE_TOOL_HEADER_RE.search(text)
        if tool_m:
            tool = tool_m.group(1).split()[0]  # "Bash command" -> "Bash"

        # Find description (first indented line)
        description = ""
        desc_m = _CLAUDE_INDENTED_RE.search(text)
        if desc_m:
            description = desc_m.group(1).strip()

        # Find approve/deny keys from numbered choices
        # "1. Yes" -> press "1", "3. No" -> press "3"
        # Default to Enter for yes (selects highlighted ❯ option)
        approve_key = "\r"
        deny_key = "3"

        yes_m = _CLAUDE_YES_CHOICE_RE.search(text)
        if yes_m:
            approve_key = yes_m.group(1)

        no_m = _CLAUDE_NO_CHOICE_RE.search(text)
        if no_m:
            deny_key = no_m.group(1)

        return PromptMatch(
            tool=tool,
            description=description,
            approve_key=approve_key,
            deny_key=deny_key,
            fingerprint=_fingerprint(tool, description),
        )

    # Try old format: "Do you want to allow Claude to use X?"
    tool_m = _CLAUDE_TOOL_OLD_RE.search(text)
    if tool_m:
        yn_m = _CLAUDE_YN_RE.search(text)
        if not yn_m:
            return None

        tool = tool_m.group(1)
        desc_m = _CLAUDE_DESC_OLD_RE.search(text)
        description = desc_m.group(1).strip() if desc_m else ""

        return PromptMatch(
            tool=tool,
            description=description,
            approve_key="y",
            deny_key="n",
            fingerprint=_fingerprint(tool, description),
        )

    return None


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
