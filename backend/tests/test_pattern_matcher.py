"""Tests for pattern_matcher module."""
import pytest

from duckdome.wrapper.pattern_matcher import match_permission_prompt, PromptMatch


class TestClaudePatterns:
    """Test Claude Code permission prompt detection."""

    def test_bash_tool_prompt(self):
        text = (
            "  \u276f Do you want to allow Claude to use Bash?\n"
            "    Command: git status\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        match = match_permission_prompt(text, "claude")
        assert match is not None
        assert match.tool == "Bash"
        assert "git status" in match.description
        assert match.approve_key == "y"
        assert match.deny_key == "n"

    def test_read_tool_prompt(self):
        text = (
            "  \u276f Do you want to allow Claude to use Read?\n"
            "    File: /home/user/project/main.py\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        match = match_permission_prompt(text, "claude")
        assert match is not None
        assert match.tool == "Read"
        assert "main.py" in match.description

    def test_edit_tool_prompt(self):
        text = (
            "  \u276f Do you want to allow Claude to use Edit?\n"
            "    File: src/app.py\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        match = match_permission_prompt(text, "claude")
        assert match is not None
        assert match.tool == "Edit"

    def test_no_match_on_regular_output(self):
        text = "Hello, I can help you with that.\nLet me read the file."
        match = match_permission_prompt(text, "claude")
        assert match is None

    def test_no_match_on_empty(self):
        match = match_permission_prompt("", "claude")
        assert match is None

    def test_fingerprint_is_stable(self):
        text = (
            "  \u276f Do you want to allow Claude to use Bash?\n"
            "    Command: git status\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        m1 = match_permission_prompt(text, "claude")
        m2 = match_permission_prompt(text, "claude")
        assert m1.fingerprint == m2.fingerprint

    def test_different_commands_different_fingerprints(self):
        text1 = (
            "  \u276f Do you want to allow Claude to use Bash?\n"
            "    Command: git status\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        text2 = (
            "  \u276f Do you want to allow Claude to use Bash?\n"
            "    Command: git commit\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        m1 = match_permission_prompt(text1, "claude")
        m2 = match_permission_prompt(text2, "claude")
        assert m1.fingerprint != m2.fingerprint

    def test_unknown_agent_returns_none(self):
        text = (
            "  \u276f Do you want to allow Claude to use Bash?\n"
            "    Command: git status\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        match = match_permission_prompt(text, "unknown_agent")
        assert match is None
