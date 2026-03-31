from __future__ import annotations

import json
import threading
import time
from pathlib import Path


_lock = threading.Lock()


def _queue_path(data_dir: Path, agent_name: str) -> Path:
    return data_dir / f"{agent_name}_queue.jsonl"


def write_queue_entry(
    data_dir: Path,
    agent_name: str,
    sender: str,
    text: str,
    channel: str,
) -> None:
    """Append a trigger entry to the agent's queue file."""
    entry = {
        "sender": sender,
        "text": text,
        "channel": channel,
        "timestamp": time.time(),
    }
    path = _queue_path(data_dir, agent_name)
    with _lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


def read_queue_entries(data_dir: Path, agent_name: str) -> list[dict]:
    """Read all pending entries and clear the queue file. Atomic consume via rename."""
    path = _queue_path(data_dir, agent_name)
    tmp = path.with_suffix(".consuming")
    with _lock:
        # Recover stale .consuming file from a previous crash
        if tmp.exists() and not path.exists():
            pass  # use the stale .consuming file directly
        elif not path.exists():
            return []
        else:
            # Atomic rename — no window where entries can be lost
            path.rename(tmp)

    try:
        text = tmp.read_text(encoding="utf-8")
    finally:
        tmp.unlink(missing_ok=True)

    entries = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass  # Skip malformed lines — don't crash the queue watcher
    return entries
