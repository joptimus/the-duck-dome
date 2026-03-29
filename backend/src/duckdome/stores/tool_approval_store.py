from __future__ import annotations

import json
import os
from pathlib import Path

from duckdome.models.tool_approval import ToolApproval, ToolPolicyDecision


class ToolApprovalStore:
    """JSONL-backed store for tool approvals + persisted per-tool policy."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._approvals_file = self._data_dir / "tool_approvals.jsonl"
        self._policy_file = self._data_dir / "tool_policy.json"
        self._approvals: dict[str, ToolApproval] = {}
        self._order: list[str] = []
        self._policy: dict[str, dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        if self._approvals_file.exists():
            with open(self._approvals_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    approval = ToolApproval(**json.loads(line))
                    self._approvals[approval.id] = approval
                    if approval.id not in self._order:
                        self._order.append(approval.id)

        if self._policy_file.exists():
            try:
                data = json.loads(self._policy_file.read_text("utf-8"))
            except Exception:
                data = {}
            if isinstance(data, dict):
                for agent, tools in data.items():
                    if not isinstance(tools, dict):
                        continue
                    cleaned: dict[str, str] = {}
                    for tool, decision in tools.items():
                        value = str(decision).strip().lower()
                        if value in (
                            ToolPolicyDecision.ALLOW.value,
                            ToolPolicyDecision.DENY.value,
                        ):
                            cleaned[str(tool)] = value
                    if cleaned:
                        self._policy[str(agent)] = cleaned

    def _save_approvals(self) -> None:
        tmp = self._approvals_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for approval_id in self._order:
                f.write(self._approvals[approval_id].model_dump_json() + "\n")
            f.flush()
            os.fsync(f.fileno())
        tmp.rename(self._approvals_file)

    def _save_policy(self) -> None:
        tmp = self._policy_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(self._policy, indent=2) + "\n")
            f.flush()
            os.fsync(f.fileno())
        tmp.rename(self._policy_file)

    def add(self, approval: ToolApproval) -> ToolApproval:
        if approval.id in self._approvals:
            return self._approvals[approval.id]
        self._approvals[approval.id] = approval
        self._order.append(approval.id)
        self._save_approvals()
        return approval

    def get(self, approval_id: str) -> ToolApproval | None:
        return self._approvals.get(approval_id)

    def update(self, approval_id: str, approval: ToolApproval) -> ToolApproval | None:
        if approval_id not in self._approvals:
            return None
        if approval.id != approval_id:
            raise ValueError(
                f"approval.id mismatch: expected {approval_id}, got {approval.id}"
            )
        self._approvals[approval_id] = approval
        self._save_approvals()
        return approval

    def list_pending(self, channel: str | None = None) -> list[ToolApproval]:
        result: list[ToolApproval] = []
        for approval_id in self._order:
            approval = self._approvals[approval_id]
            if approval.status != "pending":
                continue
            if channel and approval.channel != channel:
                continue
            result.append(approval)
        return result

    def get_policy(self, agent: str, tool: str) -> str | None:
        return self._policy.get(agent, {}).get(tool)

    def set_policy(self, agent: str, tool: str, decision: str) -> None:
        normalized = decision.strip().lower()
        if normalized not in (
            ToolPolicyDecision.ALLOW.value,
            ToolPolicyDecision.DENY.value,
        ):
            raise ValueError(f"Invalid policy decision: {decision}")
        self._policy.setdefault(agent, {})[tool] = normalized
        self._save_policy()
