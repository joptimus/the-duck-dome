from __future__ import annotations

from dataclasses import dataclass

from duckdome.models.agent_permissions import (
    AgentPermissions,
    AutoApprovePolicy,
    ToolPermission,
)
from duckdome.stores.agent_permission_store import AgentPermissionStore
from duckdome.stores.base import BaseChannelStore


DEFAULT_TOOL_CATALOG = [
    ToolPermission(
        key="bash",
        label="Terminal / bash",
        description="Run shell commands",
        icon="TerminalIcon",
        enabled=True,
        highRisk=True,
    ),
    ToolPermission(
        key="write_file",
        label="Write files",
        description="Create and modify files",
        icon="EditIcon",
        enabled=True,
        highRisk=True,
    ),
    ToolPermission(
        key="read_file",
        label="Read files",
        description="View file contents",
        icon="EyeIcon",
        enabled=True,
        highRisk=False,
    ),
    ToolPermission(
        key="web_search",
        label="Web search",
        description="Search the internet",
        icon="SearchIcon",
        enabled=False,
        highRisk=False,
    ),
]


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    auto_approved: bool = False
    permission_key: str | None = None
    reason: str | None = None


class AgentPermissionService:
    """Resolves persisted per-agent permissions and runtime tool checks."""

    def __init__(
        self,
        store: AgentPermissionStore,
        channel_store: BaseChannelStore | None = None,
        tool_catalog: list[ToolPermission] | None = None,
    ) -> None:
        self._store = store
        self._channel_store = channel_store
        self._tool_catalog = tool_catalog or DEFAULT_TOOL_CATALOG

    def list_tool_catalog(self) -> list[ToolPermission]:
        return [tool.model_copy(deep=True) for tool in self._tool_catalog]

    def _catalog_by_key(self) -> dict[str, ToolPermission]:
        return {tool.key: tool for tool in self._tool_catalog}

    def get_agent_permissions(self, agent: str) -> AgentPermissions:
        stored = self._store.get(agent) or {}
        stored_tools = stored.get("tools", {})
        tools = []
        for tool in self._tool_catalog:
            tools.append(
                ToolPermission(
                    key=tool.key,
                    label=tool.label,
                    description=tool.description,
                    icon=tool.icon,
                    enabled=bool(stored_tools.get(tool.key, tool.enabled)),
                    highRisk=tool.highRisk,
                )
            )
        return AgentPermissions(
            tools=tools,
            autoApprove=AutoApprovePolicy(stored.get("autoApprove", AutoApprovePolicy.NONE.value)),
            maxLoops=stored.get("maxLoops", 25),
        )

    def update_agent_permissions(
        self,
        agent: str,
        *,
        tools: list[dict] | None = None,
        auto_approve: str | None = None,
        max_loops: int | None = None,
    ) -> AgentPermissions:
        current = self.get_agent_permissions(agent)
        enabled_by_key = {tool.key: tool.enabled for tool in current.tools}
        if isinstance(tools, list):
            for entry in tools:
                key = str(entry.get("key", "")).strip()
                if key in enabled_by_key:
                    enabled_by_key[key] = bool(entry.get("enabled", False))

        next_auto_approve = current.autoApprove.value if auto_approve is None else str(auto_approve).lower()
        if next_auto_approve not in {
            AutoApprovePolicy.NONE.value,
            AutoApprovePolicy.TOOL.value,
            AutoApprovePolicy.ALL.value,
        }:
            next_auto_approve = AutoApprovePolicy.NONE.value

        next_max_loops = current.maxLoops if max_loops is None else max_loops
        next_max_loops = max(1, min(100, int(next_max_loops)))

        self._store.set(
            agent,
            {
                "tools": enabled_by_key,
                "autoApprove": next_auto_approve,
                "maxLoops": next_max_loops,
            },
        )
        return self.get_agent_permissions(agent)

    def get_channel_max_loops(self, channel_id: str) -> int:
        if self._channel_store is None:
            return 25
        agents = self._channel_store.list_agents(channel_id)
        if not agents:
            return 25
        return min(self.get_agent_permissions(agent.agent_type).maxLoops for agent in agents)

    def resolve_permission_key(self, runtime_tool_name: str, tool_input: dict | None = None) -> str | None:
        name = str(runtime_tool_name or "").strip().lower()
        if not name:
            return None
        if name in self._catalog_by_key():
            return name
        if name in {"local_shell", "commandexecution", "command_execution", "bash", "shell"}:
            return "bash"
        if name in {"apply_patch", "filechange", "file_change", "write", "edit"}:
            return "write_file"
        if name in {"read", "read_file", "view_file"}:
            return "read_file"
        if name in {"web_search", "search", "browser_search"}:
            return "web_search"

        params = tool_input or {}
        command = str(params.get("command") or params.get("cmd") or "").strip().lower()
        if command:
            return "bash"
        path = str(params.get("path") or "").strip()
        if path:
            return "write_file"
        return None

    def evaluate_tool_use(
        self,
        *,
        agent: str,
        runtime_tool_name: str,
        tool_input: dict | None = None,
    ) -> PermissionDecision:
        permission_key = self.resolve_permission_key(runtime_tool_name, tool_input)
        if permission_key is None:
            return PermissionDecision(allowed=True, permission_key=None)

        permissions = self.get_agent_permissions(agent)
        tool = next((item for item in permissions.tools if item.key == permission_key), None)
        if tool is None:
            return PermissionDecision(allowed=True, permission_key=permission_key)
        if not tool.enabled:
            return PermissionDecision(
                allowed=False,
                permission_key=permission_key,
                reason=f"{permission_key} is disabled for {agent}",
            )
        if permissions.autoApprove in {AutoApprovePolicy.TOOL, AutoApprovePolicy.ALL}:
            return PermissionDecision(
                allowed=True,
                auto_approved=True,
                permission_key=permission_key,
            )
        return PermissionDecision(allowed=True, permission_key=permission_key)
