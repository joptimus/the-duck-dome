from pathlib import Path

import pytest

from duckdome.wrapper.providers import build_launch_args


def test_claude_launch_args():
    result = build_launch_args(
        agent_type="claude",
        mcp_config_path=Path("/tmp/mcp-config-claude.json"),
        cwd=None,
    )
    assert result.cmd[0] == "claude"
    assert "--mcp-config" in result.cmd
    assert any("mcp-config-claude.json" in arg for arg in result.cmd)
    # Should NOT have --print (persistent mode)
    assert "--print" not in result.cmd
    # No dangerous permissions flags
    assert "--dangerously-skip-permissions" not in result.cmd


def test_codex_launch_args():
    result = build_launch_args(
        agent_type="codex",
        mcp_config_path=Path("/tmp/mcp-config-codex.json"),
        cwd=None,
        mcp_url="http://localhost:8200/mcp",
    )
    assert result.cmd[0] == "codex"
    # Codex uses -c flags, not --mcp-config
    assert "-c" in result.cmd
    assert any("http://localhost:8200/mcp" in arg for arg in result.cmd)
    # No dangerous permissions flags
    assert "--dangerously-bypass-approvals-and-sandbox" not in result.cmd


def test_unknown_agent_raises():
    with pytest.raises(ValueError, match="Unknown agent type"):
        build_launch_args("unknown", Path("/tmp/x.json"), None)
