from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from duckdome.models.agent_permissions import AutoApprovePolicy


class AgentPermissionStore:
    """Persisted per-agent permissions configuration."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._file = self._data_dir / "agent_permissions.json"
        self._lock = threading.RLock()
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self._file.exists():
                return
            try:
                raw = json.loads(self._file.read_text("utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                return
            if not isinstance(raw, dict):
                return

            cleaned: dict[str, dict] = {}
            for agent, value in raw.items():
                if not isinstance(value, dict):
                    continue
                tools = value.get("tools", {})
                normalized_tools = {}
                if isinstance(tools, dict):
                    for key, enabled in tools.items():
                        if isinstance(key, str):
                            normalized_tools[key] = bool(enabled)
                auto_approve = str(value.get("autoApprove", AutoApprovePolicy.NONE.value)).lower()
                if auto_approve not in {
                    AutoApprovePolicy.NONE.value,
                    AutoApprovePolicy.TOOL.value,
                    AutoApprovePolicy.ALL.value,
                }:
                    auto_approve = AutoApprovePolicy.NONE.value
                try:
                    max_loops = max(1, min(100, int(value.get("maxLoops", 25))))
                except (TypeError, ValueError):
                    max_loops = 25

                cleaned[str(agent)] = {
                    "tools": normalized_tools,
                    "autoApprove": auto_approve,
                    "maxLoops": max_loops,
                }
            self._data = cleaned

    def _save(self) -> None:
        tmp = self._file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(self._data, indent=2) + "\n")
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(self._file)

    def get(self, agent: str) -> dict | None:
        with self._lock:
            value = self._data.get(agent)
            if value is None:
                return None
            return {
                "tools": dict(value.get("tools", {})),
                "autoApprove": value.get("autoApprove", AutoApprovePolicy.NONE.value),
                "maxLoops": value.get("maxLoops", 25),
            }

    def set(self, agent: str, payload: dict) -> dict:
        with self._lock:
            tools = payload.get("tools", {})
            normalized_tools = {}
            if isinstance(tools, dict):
                for key, enabled in tools.items():
                    if isinstance(key, str):
                        normalized_tools[key] = bool(enabled)

            auto_approve = str(
                payload.get("autoApprove", AutoApprovePolicy.NONE.value)
            ).lower()
            if auto_approve not in {
                AutoApprovePolicy.NONE.value,
                AutoApprovePolicy.TOOL.value,
                AutoApprovePolicy.ALL.value,
            }:
                auto_approve = AutoApprovePolicy.NONE.value

            try:
                max_loops = max(1, min(100, int(payload.get("maxLoops", 25))))
            except (TypeError, ValueError):
                max_loops = 25

            self._data[agent] = {
                "tools": normalized_tools,
                "autoApprove": auto_approve,
                "maxLoops": max_loops,
            }
            self._save()
            return self.get(agent) or {}
