"""Tests for pattern_matcher module."""
from duckdome.wrapper.pattern_matcher import match_permission_prompt


class TestClaudeNewFormat:
    """Test Claude Code's current permission prompt format (numbered choices)."""

    def test_bash_command_prompt(self):
        text = (
            " Bash command\n"
            "   ls /c/Users/James/Downloads 2>&1 | head -20\n"
            "   List Downloads folder contents\n"
            " Do you want to proceed?\n"
            " \u276f 1. Yes\n"
            "   2. Yes, allow reading from Downloads\\ from this project\n"
            "   3. No\n"
        )
        match = match_permission_prompt(text, "claude")
        assert match is not None
        assert match.tool == "Bash"
        assert "Downloads" in match.description
        assert match.approve_key == "1"
        assert match.deny_key == "3"

    def test_read_file_prompt(self):
        text = (
            " Read file\n"
            "   /home/user/project/main.py\n"
            " Do you want to proceed?\n"
            " \u276f 1. Yes\n"
            "   2. No\n"
        )
        match = match_permission_prompt(text, "claude")
        assert match is not None
        assert match.tool == "Read"
        assert "main.py" in match.description
        assert match.deny_key == "2"

    def test_edit_file_prompt(self):
        text = (
            " Edit file\n"
            "   src/app.py\n"
            " Do you want to proceed?\n"
            " \u276f 1. Yes\n"
            "   2. No\n"
        )
        match = match_permission_prompt(text, "claude")
        assert match is not None
        assert match.tool == "Edit"

    def test_no_match_on_regular_output(self):
        text = "Hello, I can help you with that.\nLet me read the file."
        assert match_permission_prompt(text, "claude") is None

    def test_no_match_on_empty(self):
        assert match_permission_prompt("", "claude") is None

    def test_fingerprint_is_stable(self):
        text = (
            " Bash command\n"
            "   git status\n"
            " Do you want to proceed?\n"
            " \u276f 1. Yes\n"
            "   2. No\n"
        )
        m1 = match_permission_prompt(text, "claude")
        m2 = match_permission_prompt(text, "claude")
        assert m1.fingerprint == m2.fingerprint

    def test_different_commands_different_fingerprints(self):
        base = (
            " Bash command\n"
            "   {cmd}\n"
            " Do you want to proceed?\n"
            " \u276f 1. Yes\n"
            "   2. No\n"
        )
        m1 = match_permission_prompt(base.format(cmd="git status"), "claude")
        m2 = match_permission_prompt(base.format(cmd="git commit"), "claude")
        assert m1.fingerprint != m2.fingerprint

    def test_unknown_agent_returns_none(self):
        text = (
            " Bash command\n"
            "   git status\n"
            " Do you want to proceed?\n"
            " \u276f 1. Yes\n"
            "   2. No\n"
        )
        assert match_permission_prompt(text, "unknown_agent") is None


class TestClaudeOldFormat:
    """Test Claude Code's older permission prompt format (Y/N)."""

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


class TestCodexPatterns:
    """Test Codex CLI permission prompt detection."""

    def test_shell_command_prompt(self):
        text = (
            "  Would you like to run the following command?\n"
            "  $ New-Item -ItemType Directory -Force -Path C:\\tmp | Out-Null\n"
            "\u203a 1. Yes, proceed (y)\n"
            "  2. Yes, and don't ask again for commands that start with `New-Item` (p)\n"
            "  3. No, and tell Codex what to do differently (esc)\n"
            "\n"
            "  Press enter to confirm or esc to cancel\n"
        )
        match = match_permission_prompt(text, "codex")
        assert match is not None
        assert match.tool == "Shell"
        assert "New-Item" in match.description
        assert match.approve_key == "y"
        assert match.deny_key == "\x1b"

    def test_no_match_on_working(self):
        text = "Working (5s \u2022 esc to interrupt)\n\ngpt-5.4 medium"
        assert match_permission_prompt(text, "codex") is None

    def test_no_match_on_empty(self):
        assert match_permission_prompt("", "codex") is None
