# backend/tests/test_mcp_config.py
import json
import tempfile
from pathlib import Path

from duckdome.wrapper.mcp_config import generate_mcp_config


def test_generate_mcp_config_creates_valid_json():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        path = generate_mcp_config(
            config_dir=config_dir,
            agent_name="claude",
            mcp_url="http://localhost:8200/mcp",
        )
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "mcpServers" in data
        assert "duckdome" in data["mcpServers"]
        assert data["mcpServers"]["duckdome"]["url"] == "http://localhost:8200/mcp"


def test_generate_mcp_config_unique_per_agent():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        p1 = generate_mcp_config(config_dir, "claude", "http://localhost:8200/mcp")
        p2 = generate_mcp_config(config_dir, "codex", "http://localhost:8200/mcp")
        assert p1 != p2
        assert "claude" in p1.name
        assert "codex" in p2.name
