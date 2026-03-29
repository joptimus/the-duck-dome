from unittest.mock import patch, MagicMock
import pytest

from duckdome.models.channel import Channel, ChannelType, AgentInstance
from duckdome.models.message import Message
from duckdome.models.trigger import Trigger, TriggerStatus
from duckdome.runner.base import RunResult
from duckdome.services.channel_service import ChannelService
from duckdome.services.message_service import MessageService
from duckdome.services.trigger_service import TriggerService
from duckdome.services.runner_service import RunnerService
from duckdome.stores.channel_store import ChannelStore
from duckdome.stores.message_store import MessageStore
from duckdome.stores.trigger_store import TriggerStore


@pytest.fixture
def all_stores(tmp_path):
    return (
        ChannelStore(data_dir=tmp_path),
        MessageStore(data_dir=tmp_path),
        TriggerStore(data_dir=tmp_path),
    )


@pytest.fixture
def services(all_stores):
    cs, ms, ts = all_stores
    channel_svc = ChannelService(store=cs)
    message_svc = MessageService(
        store=ms, known_agents=["claude"], channel_service=channel_svc,
    )
    trigger_svc = TriggerService(trigger_store=ts, channel_store=cs)
    runner_svc = RunnerService(
        trigger_service=trigger_svc,
        message_service=message_svc,
        channel_store=cs,
        message_store=ms,
    )
    return channel_svc, message_svc, trigger_svc, runner_svc


@pytest.fixture
def setup_channel(services, all_stores):
    """Create channel, register agent, send message, create trigger."""
    channel_svc, message_svc, trigger_svc, _ = services
    cs, ms, ts = all_stores
    ch = channel_svc.create_channel(name="general", type="general")
    trigger_svc.register_agent(ch.id, "claude")
    msg = message_svc.send(text="@claude help me", channel=ch.id, sender="human")
    trigger_svc.create_trigger(ch.id, "claude", msg.id)
    return ch, msg


@patch("duckdome.services.runner_service.get_executor")
def test_execute_next_success(mock_exec, services, setup_channel, all_stores):
    _, _, _, runner_svc = services
    ch, msg = setup_channel
    cs, ms, _ = all_stores

    mock_exec.return_value.execute.return_value = RunResult(
        stdout="Here is my answer", stderr="", exit_code=0, duration_ms=500,
    )

    run = runner_svc.execute_next(ch.id, "claude")
    assert run is not None
    assert run.exit_code == 0
    assert run.duration_ms == 500
    assert run.error_summary is None

    # Response should be posted to channel
    msgs = ms.list_by_channel(ch.id)
    assert any(m.sender == "claude" and "Here is my answer" in m.text for m in msgs)

    # Agent should be idle
    agent = cs.get_agent(f"{ch.id}:claude")
    assert agent.status == "idle"


@patch("duckdome.services.runner_service.get_executor")
def test_execute_next_failure(mock_exec, services, setup_channel, all_stores):
    _, _, _, runner_svc = services
    ch, _ = setup_channel
    cs, _, _ = all_stores

    mock_exec.return_value.execute.return_value = RunResult(
        stdout="", stderr="model error", exit_code=1, duration_ms=200,
    )

    run = runner_svc.execute_next(ch.id, "claude")
    assert run is not None
    assert run.exit_code == 1
    assert run.error_summary == "model error"

    agent = cs.get_agent(f"{ch.id}:claude")
    assert agent.status == "idle"
    assert agent.last_error is not None


def test_execute_next_no_triggers(services):
    channel_svc, _, trigger_svc, runner_svc = services
    ch = channel_svc.create_channel(name="empty", type="general")
    trigger_svc.register_agent(ch.id, "claude")

    run = runner_svc.execute_next(ch.id, "claude")
    assert run is None


@patch("duckdome.services.runner_service.get_executor")
def test_execute_next_exception(mock_exec, services, setup_channel):
    _, _, _, runner_svc = services
    ch, _ = setup_channel

    mock_exec.return_value.execute.side_effect = RuntimeError("unexpected crash")

    run = runner_svc.execute_next(ch.id, "claude")
    assert run is not None
    assert run.exit_code == -99
    assert "unexpected crash" in run.error_summary
