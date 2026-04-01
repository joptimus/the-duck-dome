from __future__ import annotations

import logging
from pathlib import Path

from duckdome.wrapper.manager import AgentProcessManager

logger = logging.getLogger(__name__)


class WrapperService:
    """Thin service layer over AgentProcessManager.

    Provides start/stop/trigger methods for use by routes and other services.
    """

    def __init__(
        self,
        data_dir: Path,
        mcp_port: int = 8200,
        tool_approval_service=None,
        ws_manager=None,
    ) -> None:
        self._manager = AgentProcessManager(
            data_dir=data_dir,
            mcp_port=mcp_port,
            tool_approval_service=tool_approval_service,
            ws_manager=ws_manager,
        )

    def start_agent(self, agent_type: str, cwd: str | None = None, channel_id: str = "") -> bool:
        return self._manager.start_agent(agent_type, cwd=cwd, channel_id=channel_id)

    def stop_agent(self, agent_type: str, channel_id: str = "") -> bool:
        return self._manager.stop_agent(agent_type, channel_id=channel_id)

    def stop_all(self) -> None:
        self._manager.stop_all()

    def trigger(self, agent_type: str, sender: str, text: str, channel: str) -> bool:
        return self._manager.trigger_agent(agent_type, sender, text, channel)

    def is_running(self, agent_type: str, channel_id: str = "") -> bool:
        return self._manager.is_running(agent_type, channel_id=channel_id)

    def get_agent_details(self, agent_type: str, channel_id: str = "") -> dict | None:
        return self._manager.get_agent_details(agent_type, channel_id=channel_id)

    def list_running(self) -> list[str]:
        return self._manager.list_running()
