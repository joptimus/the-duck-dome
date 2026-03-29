import pytest
from duckdome.models.channel import Channel, ChannelType, AgentInstance
from duckdome.models.message import Message
from duckdome.models.trigger import Trigger
from duckdome.stores.channel_store import ChannelStore
from duckdome.stores.message_store import MessageStore
from duckdome.runner.context import build_context, build_prompt, _repo_preflight


@pytest.fixture
def stores(tmp_path):
    return ChannelStore(data_dir=tmp_path), MessageStore(data_dir=tmp_path)


@pytest.fixture
def general_channel(stores):
    cs, ms = stores
    ch = Channel(name="planning", type=ChannelType.GENERAL)
    cs.add_channel(ch)
    cs.add_agent(AgentInstance(channel_id=ch.id, agent_type="claude", status="idle"))
    return ch


@pytest.fixture
def repo_channel(stores, tmp_path):
    cs, ms = stores
    repo = tmp_path / "my-repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    ch = Channel(name="my-repo", type=ChannelType.REPO, repo_path=str(repo))
    cs.add_channel(ch)
    cs.add_agent(AgentInstance(channel_id=ch.id, agent_type="claude", status="idle"))
    return ch


def test_build_context_general(stores, general_channel):
    cs, ms = stores
    ch = general_channel
    ms.add(Message(text="hello", channel=ch.id, sender="human"))
    ms.add(Message(text="hi there", channel=ch.id, sender="claude"))
    source = Message(text="@claude help me plan", channel=ch.id, sender="human")
    ms.add(source)

    trigger = Trigger(
        channel_id=ch.id, target_agent_type="claude", source_message_id=source.id,
    )
    ctx = build_context(trigger, cs, ms)
    assert ctx.channel.channel_id == ch.id
    assert ctx.channel.channel_type == "general"
    assert ctx.channel.repo_path is None
    assert ctx.trigger.text == "@claude help me plan"
    assert len(ctx.history) == 2
    assert ctx.repo_preflight is None


def test_build_context_repo(stores, repo_channel):
    cs, ms = stores
    ch = repo_channel
    source = Message(text="@claude review the code", channel=ch.id, sender="human")
    ms.add(source)

    trigger = Trigger(
        channel_id=ch.id, target_agent_type="claude", source_message_id=source.id,
    )
    ctx = build_context(trigger, cs, ms)
    assert ctx.channel.channel_type == "repo"
    assert ctx.channel.repo_path is not None
    assert ctx.repo_preflight is not None
    assert ctx.repo_preflight.valid is True


def test_history_limited_to_12(stores, general_channel):
    cs, ms = stores
    ch = general_channel
    for i in range(20):
        ms.add(Message(text=f"msg-{i}", channel=ch.id, sender="human"))
    source = Message(text="@claude final", channel=ch.id, sender="human")
    ms.add(source)

    trigger = Trigger(
        channel_id=ch.id, target_agent_type="claude", source_message_id=source.id,
    )
    ctx = build_context(trigger, cs, ms)
    assert len(ctx.history) == 12
    assert ctx.history[0]["text"] == "msg-8"
    assert ctx.history[-1]["text"] == "msg-19"


def test_build_prompt_general(stores, general_channel):
    cs, ms = stores
    ch = general_channel
    source = Message(text="@claude help", channel=ch.id, sender="human")
    ms.add(source)
    trigger = Trigger(
        channel_id=ch.id, target_agent_type="claude", source_message_id=source.id
    )
    ctx = build_context(trigger, cs, ms)
    prompt = build_prompt(ctx)
    assert "general channel" in prompt
    assert "no repo binding" in prompt
    assert "@claude help" in prompt
    assert "Make progress" in prompt


def test_build_prompt_repo(stores, repo_channel):
    cs, ms = stores
    ch = repo_channel
    source = Message(text="@claude review", channel=ch.id, sender="human")
    ms.add(source)
    trigger = Trigger(
        channel_id=ch.id, target_agent_type="claude", source_message_id=source.id
    )
    ctx = build_context(trigger, cs, ms)
    prompt = build_prompt(ctx)
    assert "repo channel" in prompt
    assert "Working directory" in prompt
    assert "do not modify files" in prompt


def test_repo_preflight_valid(tmp_path):
    repo = tmp_path / "valid-repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    result = _repo_preflight(str(repo))
    assert result.valid is True


def test_repo_preflight_not_dir(tmp_path):
    result = _repo_preflight(str(tmp_path / "nonexistent"))
    assert result.valid is False
    assert "does not exist" in result.error


def test_repo_preflight_not_git(tmp_path):
    d = tmp_path / "not-git"
    d.mkdir()
    result = _repo_preflight(str(d))
    assert result.valid is False
    assert "not a git" in result.error
