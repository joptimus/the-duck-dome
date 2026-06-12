"""Stores must survive corrupt persisted data and concurrent writers.

Covers review findings 1-C1 (no locking on stores written from multiple
threads) and 1-C2 (one torn JSONL line prevents the backend from booting).
"""

import threading

import pytest

from duckdome.models.channel import AgentInstance, Channel, ChannelType
from duckdome.models.job import Job
from duckdome.models.message import Message
from duckdome.models.rule import Rule
from duckdome.models.tool_approval import ToolApproval
from duckdome.models.trigger import Trigger
from duckdome.stores.channel_store import ChannelStore
from duckdome.stores.job_store import JobStore
from duckdome.stores.message_store import MessageStore
from duckdome.stores.repo_store import RepoStore
from duckdome.stores.rule_store import RuleStore
from duckdome.stores.tool_approval_store import ToolApprovalStore
from duckdome.stores.trigger_store import TriggerStore

CORRUPT_LINES = [
    "not json at all",
    '{"truncated": "li',  # torn line from a crash mid-append
    '{"valid_json": "but wrong schema"}',
]


def _write_jsonl(path, good_lines):
    lines = [good_lines[0], *CORRUPT_LINES, *good_lines[1:]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_message_store_skips_corrupt_lines(tmp_path):
    m1 = Message(text="one", channel="general", sender="human")
    m2 = Message(text="two", channel="general", sender="human")
    _write_jsonl(tmp_path / "messages.jsonl", [m1.model_dump_json(), m2.model_dump_json()])

    store = MessageStore(data_dir=tmp_path)

    loaded = store.list_by_channel("general")
    assert [m.id for m in loaded] == [m1.id, m2.id]


def test_message_store_rewrite_after_corrupt_load_drops_bad_lines(tmp_path):
    m1 = Message(text="one", channel="general", sender="human")
    m2 = Message(text="two", channel="general", sender="human")
    _write_jsonl(tmp_path / "messages.jsonl", [m1.model_dump_json(), m2.model_dump_json()])

    store = MessageStore(data_dir=tmp_path)
    store.update(m1.id, m1)  # forces a rewrite

    reloaded = MessageStore(data_dir=tmp_path)
    assert [m.id for m in reloaded.list_by_channel("general")] == [m1.id, m2.id]


def test_job_store_skips_corrupt_lines(tmp_path):
    j1 = Job(title="a", channel="general", created_by="human")
    j2 = Job(title="b", channel="general", created_by="human")
    _write_jsonl(tmp_path / "jobs.jsonl", [j1.model_dump_json(), j2.model_dump_json()])

    store = JobStore(data_dir=tmp_path)

    assert [j.id for j in store.list_jobs()] == [j1.id, j2.id]


def test_rule_store_skips_corrupt_lines(tmp_path):
    r1 = Rule(text="rule one")
    r2 = Rule(text="rule two")
    _write_jsonl(tmp_path / "rules.jsonl", [r1.model_dump_json(), r2.model_dump_json()])

    store = RuleStore(data_dir=tmp_path)

    assert [r.id for r in store.list_all()] == [r1.id, r2.id]


def test_trigger_store_skips_corrupt_lines(tmp_path):
    t1 = Trigger(channel_id="general", target_agent_type="claude", source_message_id="m1")
    t2 = Trigger(channel_id="general", target_agent_type="codex", source_message_id="m2")
    _write_jsonl(tmp_path / "triggers.jsonl", [t1.model_dump_json(), t2.model_dump_json()])

    store = TriggerStore(data_dir=tmp_path)

    assert [t.id for t in store.list_by_channel("general")] == [t1.id, t2.id]


def test_tool_approval_store_skips_corrupt_lines(tmp_path):
    a1 = ToolApproval(agent="claude", tool="Bash", channel="general")
    a2 = ToolApproval(agent="codex", tool="Read", channel="general")
    _write_jsonl(
        tmp_path / "tool_approvals.jsonl", [a1.model_dump_json(), a2.model_dump_json()]
    )

    store = ToolApprovalStore(data_dir=tmp_path)

    assert [a.id for a in store.list_pending()] == [a1.id, a2.id]


def test_channel_store_skips_corrupt_lines(tmp_path):
    c1 = Channel(name="general", type=ChannelType.GENERAL)
    c2 = Channel(name="random", type=ChannelType.GENERAL)
    _write_jsonl(tmp_path / "channels.jsonl", [c1.model_dump_json(), c2.model_dump_json()])
    a1 = AgentInstance(channel_id=c1.id, agent_type="claude")
    a2 = AgentInstance(channel_id=c2.id, agent_type="codex")
    _write_jsonl(tmp_path / "agents.jsonl", [a1.model_dump_json(), a2.model_dump_json()])

    store = ChannelStore(data_dir=tmp_path)

    assert [c.id for c in store.list_channels()] == [c1.id, c2.id]
    assert store.get_agent(a1.id) is not None
    assert store.get_agent(a2.id) is not None


def test_repo_store_survives_corrupt_json(tmp_path):
    (tmp_path / "repo_sources.json").write_text("{corrupt", encoding="utf-8")
    (tmp_path / "repo_hidden.json").write_text("[truncat", encoding="utf-8")

    store = RepoStore(data_dir=tmp_path)

    assert store.list_sources() == []
    assert store.list_hidden() == set()


def test_message_store_concurrent_adds_and_updates_lose_nothing(tmp_path):
    """Concurrent add() (append) and update() (full rewrite) must not lose
    messages on disk. Without locking, a rewrite snapshotting mid-add clobbers
    concurrently appended lines."""
    store = MessageStore(data_dir=tmp_path)
    seed = Message(text="seed", channel="general", sender="human")
    store.add(seed)

    n_threads = 8
    per_thread = 25
    errors = []

    def writer(thread_idx):
        try:
            for i in range(per_thread):
                msg = Message(
                    text=f"t{thread_idx}-{i}", channel="general", sender="human"
                )
                store.add(msg)
                store.update(seed.id, seed)
        except Exception as exc:  # pragma: no cover - failure detail
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    expected = 1 + n_threads * per_thread
    assert len(store.list_by_channel("general")) == expected
    reloaded = MessageStore(data_dir=tmp_path)
    assert len(reloaded.list_by_channel("general")) == expected


def test_job_store_concurrent_adds_lose_nothing(tmp_path):
    store = JobStore(data_dir=tmp_path)
    seed = Job(title="seed", channel="general", created_by="human")
    store.add(seed)

    n_threads = 8
    per_thread = 25
    errors = []

    def writer(thread_idx):
        try:
            for i in range(per_thread):
                store.add(
                    Job(title=f"t{thread_idx}-{i}", channel="general", created_by="human")
                )
                store.update(seed.id, seed)
        except Exception as exc:  # pragma: no cover - failure detail
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    expected = 1 + n_threads * per_thread
    assert len(store.list_jobs()) == expected
    assert len(JobStore(data_dir=tmp_path).list_jobs()) == expected
