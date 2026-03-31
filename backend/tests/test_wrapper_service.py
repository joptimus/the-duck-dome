import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from duckdome.services.wrapper_service import WrapperService


def test_trigger_writes_queue_entry():
    """WrapperService.trigger should write a queue file entry."""
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        svc = WrapperService(data_dir=data_dir)

        # Mock the manager to say agent is running
        svc._manager.is_running = MagicMock(return_value=True)
        svc._manager.trigger_agent = MagicMock(return_value=True)

        result = svc.trigger(agent_type="claude", sender="user", text="hello", channel="general")
        assert result is True
        svc._manager.trigger_agent.assert_called_once_with("claude", "user", "hello", "general")


def test_trigger_returns_false_when_agent_not_running():
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        svc = WrapperService(data_dir=data_dir)
        svc._manager.is_running = MagicMock(return_value=False)
        svc._manager.trigger_agent = MagicMock(return_value=False)

        result = svc.trigger(agent_type="claude", sender="user", text="hello", channel="general")
        assert result is False
