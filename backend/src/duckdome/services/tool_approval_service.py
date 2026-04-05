from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from duckdome.models.tool_approval import ToolApproval, ToolApprovalStatus
from duckdome.services.agent_permission_service import AgentPermissionService
from duckdome.stores.tool_approval_store import ToolApprovalStore
from duckdome.ws.events import TOOL_APPROVAL_UPDATED

if TYPE_CHECKING:
    from duckdome.ws.manager import ConnectionManager


class ToolApprovalService:
    def __init__(
        self,
        store: ToolApprovalStore,
        permission_service: AgentPermissionService | None = None,
        ws_manager: ConnectionManager | None = None,
    ) -> None:
        self._store = store
        self._permission_service = permission_service
        self._ws_manager = ws_manager
        self._runtime_resolvers: dict[str, Callable[[str, str | None], None]] = {}

    def _broadcast(self, approval: ToolApproval) -> None:
        if self._ws_manager is None:
            return
        self._ws_manager.broadcast_sync(
            {
                "type": TOOL_APPROVAL_UPDATED,
                "approval": approval.model_dump(mode="json"),
            }
        )

    @dataclass(frozen=True)
    class RequestResult:
        status: str
        source: str | None = None
        approval: ToolApproval | None = None

    def _get_policy_with_fallback(
        self,
        *,
        agent: str,
        tool: str,
        fallback_tool: str | None = None,
    ) -> str | None:
        policy = self._store.get_policy(agent, tool)
        if policy is None and fallback_tool and fallback_tool != tool:
            policy = self._store.get_policy(agent, fallback_tool)
        return policy

    def request(
        self,
        *,
        agent: str,
        tool: str,
        arguments: dict | None,
        channel: str,
    ) -> RequestResult:
        normalized_tool = tool
        if self._permission_service is not None:
            decision = self._permission_service.evaluate_tool_use(
                agent=agent,
                runtime_tool_name=tool,
                tool_input=arguments,
            )
            if not decision.allowed:
                return self.RequestResult(status="denied", source="permissions")
            if decision.permission_key:
                normalized_tool = decision.permission_key
            if decision.auto_approved:
                return self.RequestResult(status="approved", source="permissions")

        policy = self._get_policy_with_fallback(
            agent=agent,
            tool=normalized_tool,
            fallback_tool=tool,
        )
        if policy == "allow":
            return self.RequestResult(status="approved", source="policy")
        if policy == "deny":
            return self.RequestResult(status="denied", source="policy")

        approval = ToolApproval(
            agent=agent,
            tool=normalized_tool,
            arguments=arguments or {},
            channel=channel,
        )
        self._store.add(approval)
        self._broadcast(approval)
        return self.RequestResult(status="pending", approval=approval)

    def get(self, approval_id: str) -> ToolApproval | None:
        return self._store.get(approval_id)

    def register_runtime_resolver(
        self,
        approval_id: str,
        resolver: Callable[[str, str | None], None],
    ) -> None:
        self._runtime_resolvers[approval_id] = resolver

    def clear_runtime_resolver(self, approval_id: str) -> None:
        self._runtime_resolvers.pop(approval_id, None)

    def _resolve_runtime(
        self,
        approval_id: str,
        *,
        decision: str,
        reason: str | None = None,
    ) -> None:
        resolver = self._runtime_resolvers.pop(approval_id, None)
        if resolver is None:
            return
        resolver(decision, reason)

    def list_pending(self, channel: str | None = None) -> list[ToolApproval]:
        return self._store.list_pending(channel=channel)

    def approve(
        self, approval_id: str, resolved_by: str, remember: bool = False
    ) -> ToolApproval | None:
        approval = self._store.get(approval_id)
        if approval is None or approval.status != ToolApprovalStatus.PENDING:
            return None
        approval.status = ToolApprovalStatus.APPROVED
        approval.resolution = "approved"
        approval.resolved_by = resolved_by
        approval.resolved_at = time.time()
        self._store.update(approval_id, approval)
        if remember:
            self.set_policy(agent=approval.agent, tool=approval.tool, decision="allow")
        self._broadcast(approval)
        self._resolve_runtime(approval_id, decision="approved")
        return approval

    def deny(
        self, approval_id: str, resolved_by: str, remember: bool = False
    ) -> ToolApproval | None:
        approval = self._store.get(approval_id)
        if approval is None or approval.status != ToolApprovalStatus.PENDING:
            return None
        approval.status = ToolApprovalStatus.DENIED
        approval.resolution = "denied"
        approval.resolved_by = resolved_by
        approval.resolved_at = time.time()
        self._store.update(approval_id, approval)
        if remember:
            self.set_policy(agent=approval.agent, tool=approval.tool, decision="deny")
        self._broadcast(approval)
        self._resolve_runtime(approval_id, decision="denied", reason="Denied by user")
        return approval

    def set_policy(self, agent: str, tool: str, decision: str) -> None:
        self._store.set_policy(agent=agent, tool=tool, decision=decision)

    def list_policies(self) -> dict[str, dict[str, str]]:
        return self._store.list_policies()

    def clear_policies(
        self, agent: str | None = None, tool: str | None = None
    ) -> int:
        if agent is None:
            return self._store.clear_all_policies()
        if tool is None:
            return 1 if self._store.clear_policy(agent=agent) else 0
        return 1 if self._store.clear_policy(agent=agent, tool=tool) else 0
