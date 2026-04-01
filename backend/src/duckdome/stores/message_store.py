from __future__ import annotations

import json
import os
from pathlib import Path

from duckdome.models.message import Message


class MessageStore:
    """Append-only JSONL message store with in-memory index."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._file = self._data_dir / "messages.jsonl"
        self._messages: dict[str, Message] = {}
        self._order: list[str] = []
        self._load()

    def _load(self) -> None:
        if not self._file.exists():
            return
        with open(self._file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                msg = Message(**json.loads(line))
                self._messages[msg.id] = msg
                if msg.id not in self._order:
                    self._order.append(msg.id)

    def _append(self, msg: Message) -> None:
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(msg.model_dump_json() + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _rewrite(self) -> None:
        tmp = self._file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for msg_id in self._order:
                f.write(self._messages[msg_id].model_dump_json() + "\n")
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(self._file)

    def add(self, msg: Message) -> Message:
        if msg.id in self._messages:
            return self._messages[msg.id]
        self._messages[msg.id] = msg
        self._order.append(msg.id)
        self._append(msg)
        return msg

    def get(self, msg_id: str) -> Message | None:
        return self._messages.get(msg_id)

    def update(self, msg_id: str, msg: Message) -> Message | None:
        if msg_id not in self._messages:
            return None
        self._messages[msg_id] = msg
        self._rewrite()
        return msg

    def delete(self, msg_id: str) -> Message | None:
        msg = self._messages.pop(msg_id, None)
        if msg is None:
            return None
        self._order = [existing_id for existing_id in self._order if existing_id != msg_id]
        self._rewrite()
        return msg

    def list_by_channel(
        self, channel: str, after_id: str | None = None
    ) -> list[Message]:
        msgs = [self._messages[mid] for mid in self._order if self._messages[mid].channel == channel]
        if after_id is not None:
            try:
                idx = next(i for i, m in enumerate(msgs) if m.id == after_id)
                msgs = msgs[idx + 1 :]
            except StopIteration:
                pass
        return msgs

    def list_by_delivery_state(self, state: str) -> list[Message]:
        result = []
        for mid in self._order:
            msg = self._messages[mid]
            if msg.delivery and msg.delivery.state == state:
                result.append(msg)
            elif msg.deliveries:
                if any(d.state == state for d in msg.deliveries):
                    result.append(msg)
        return result
