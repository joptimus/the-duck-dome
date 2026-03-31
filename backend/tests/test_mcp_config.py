# backend/tests/test_mcp_config.py
import json
import shutil
import uuid
from pathlib import Path

from duckdome.wrapper.mcp_config import generate_gemini_settings, generate_mcp_config


def _make_local_config_dir() -> Path:
    path = Path("backend/.tmp_test_mcp_config") / str(uuid.uuid4())
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_generate_mcp_config_creates_valid_json():
    config_dir = _make_local_config_dir()
    try:
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
        assert data["mcpServers"]["duckdome"]["type"] == "http"
    finally:
        shutil.rmtree(config_dir, ignore_errors=True)


def test_generate_mcp_config_unique_per_agent():
    config_dir = _make_local_config_dir()
    try:
        p1 = generate_mcp_config(config_dir, "claude", "http://localhost:8200/mcp")
        p2 = generate_mcp_config(config_dir, "codex", "http://localhost:8200/mcp")
        assert p1 != p2
        assert "claude" in p1.name
        assert "codex" in p2.name
    finally:
        shutil.rmtree(config_dir, ignore_errors=True)


def test_generate_gemini_settings_marks_duckdome_trusted():
    config_dir = _make_local_config_dir()
    try:
        path = generate_gemini_settings(
            config_dir=config_dir,
            agent_name="gemini",
            mcp_url="http://localhost:8200/mcp",
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["mcpServers"]["duckdome"]["httpUrl"] == "http://localhost:8200/mcp"
        assert data["mcpServers"]["duckdome"]["type"] == "http"
        assert data["mcpServers"]["duckdome"]["trust"] is True
        assert data["security"]["folderTrust"]["enabled"] is True
    finally:
        shutil.rmtree(config_dir, ignore_errors=True)
