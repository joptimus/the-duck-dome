import json
import tempfile
from pathlib import Path

from duckdome.wrapper.queue import write_queue_entry, read_queue_entries


def test_write_queue_entry_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        write_queue_entry(
            data_dir=data_dir,
            agent_name="claude",
            sender="user",
            text="fix the bug",
            channel="general",
        )
        queue_file = data_dir / "claude_queue.jsonl"
        assert queue_file.exists()
        lines = queue_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["sender"] == "user"
        assert entry["text"] == "fix the bug"
        assert entry["channel"] == "general"


def test_read_queue_entries_returns_and_clears():
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        write_queue_entry(data_dir, "claude", "user", "msg1", "general")
        write_queue_entry(data_dir, "claude", "user", "msg2", "general")

        entries = read_queue_entries(data_dir, "claude")
        assert len(entries) == 2
        assert entries[0]["text"] == "msg1"
        assert entries[1]["text"] == "msg2"

        # Queue file should be cleared after read
        entries2 = read_queue_entries(data_dir, "claude")
        assert len(entries2) == 0


def test_read_queue_entries_empty_when_no_file():
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        entries = read_queue_entries(data_dir, "claude")
        assert entries == []
