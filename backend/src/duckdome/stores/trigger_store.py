from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from duckdome.models.trigger import Trigger, TriggerStatus


class TriggerStore:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._file = self._data_dir / "triggers.jsonl"
        self._lock = threading.Lock()
        self._triggers: dict[str, Trigger] = {}
        self._order: list[str] = []
        self._dedupe_index: dict[str, str] = {}  # dedupe_key -> trigger_id
        self._load()

    def _load(self) -> None:
        if not self._file.exists():
            return
        with open(self._file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                t = Trigger(**json.loads(line))
                self._triggers[t.id] = t
                if t.id not in self._order:
                    self._order.append(t.id)
                self._dedupe_index[t.dedupe_key] = t.id

    def _save(self) -> None:
        tmp = self._file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for tid in self._order:
                f.write(self._triggers[tid].model_dump_json() + "\n")
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(self._file)

    def add(self, trigger: Trigger) -> Trigger:
        with self._lock:
            if trigger.dedupe_key in self._dedupe_index:
                return self._triggers[self._dedupe_index[trigger.dedupe_key]]
            self._triggers[trigger.id] = trigger
            self._order.append(trigger.id)
            self._dedupe_index[trigger.dedupe_key] = trigger.id
            self._save()
            return trigger

    def get(self, trigger_id: str) -> Trigger | None:
        return self._triggers.get(trigger_id)

    def update(self, trigger_id: str, trigger: Trigger) -> Trigger | None:
        with self._lock:
            if trigger_id not in self._triggers:
                return None
            if trigger.id != trigger_id:
                raise ValueError(
                    f"trigger.id mismatch: expected {trigger_id}, got {trigger.id}"
                )
            self._triggers[trigger_id] = trigger
            self._save()
            return trigger

    def list_by_channel(
        self, channel_id: str, status: str | None = None
    ) -> list[Trigger]:
        result = []
        for tid in self._order:
            t = self._triggers[tid]
            if t.channel_id != channel_id:
                continue
            if status and t.status != status:
                continue
            result.append(t)
        return result

    def list_by_agent(
        self, agent_instance_id: str, status: str | None = None
    ) -> list[Trigger]:
        result = []
        for tid in self._order:
            t = self._triggers[tid]
            if t.target_agent_instance_id != agent_instance_id:
                continue
            if status and t.status != status:
                continue
            result.append(t)
        return result

    def find_by_dedupe_key(self, dedupe_key: str) -> Trigger | None:
        tid = self._dedupe_index.get(dedupe_key)
        if tid:
            return self._triggers.get(tid)
        return None
