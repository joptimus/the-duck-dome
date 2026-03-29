"""Tests for the LoopGuard and its integration in MessageService.

This feature replaces the loop guard in the legacy router
(agentchattr/apps/server/src/router.py).

Differences from legacy behavior:
- Standalone LoopGuard class instead of being embedded in Router.
- No guard_emitted flag; system message posted once on trigger,
  then paused state silently blocks further agent messages.
- Simplified: human messages reset the guard (no separate continue_routing).
"""

import pytest

from duckdome.models.message import MessageType
from duckdome.services.message_service import LoopGuard, MessageService
from duckdome.stores.message_store import MessageStore

AGENTS = ["claude", "codex", "gemini"]


# --- LoopGuard unit tests ---


class TestLoopGuard:
    def test_human_message_always_passes(self):
        guard = LoopGuard(max_hops=4)
        assert guard.check("ch1", "human", AGENTS) is True

    def test_agent_messages_within_limit_pass(self):
        guard = LoopGuard(max_hops=4)
        for _ in range(4):
            assert guard.check("ch1", "claude", AGENTS) is True

    def test_agent_messages_over_limit_blocked(self):
        guard = LoopGuard(max_hops=4)
        for _ in range(4):
            guard.check("ch1", "claude", AGENTS)
        # 5th agent hop triggers the guard
        assert guard.check("ch1", "claude", AGENTS) is False

    def test_paused_blocks_subsequent_agent_messages(self):
        guard = LoopGuard(max_hops=2)
        guard.check("ch1", "claude", AGENTS)
        guard.check("ch1", "codex", AGENTS)
        # 3rd hop triggers guard
        assert guard.check("ch1", "claude", AGENTS) is False
        # Further agent messages silently blocked
        assert guard.check("ch1", "codex", AGENTS) is False

    def test_human_message_resets_guard(self):
        guard = LoopGuard(max_hops=2)
        guard.check("ch1", "claude", AGENTS)
        guard.check("ch1", "codex", AGENTS)
        guard.check("ch1", "claude", AGENTS)  # triggers guard
        assert guard.is_paused("ch1") is True

        # Human resets
        assert guard.check("ch1", "human", AGENTS) is True
        assert guard.is_paused("ch1") is False
        assert guard.hop_count("ch1") == 0

    def test_per_channel_isolation(self):
        guard = LoopGuard(max_hops=2)
        guard.check("ch1", "claude", AGENTS)
        guard.check("ch1", "codex", AGENTS)
        guard.check("ch1", "claude", AGENTS)  # triggers guard on ch1
        assert guard.is_paused("ch1") is True
        # ch2 is unaffected
        assert guard.is_paused("ch2") is False
        assert guard.check("ch2", "claude", AGENTS) is True

    def test_reset_method(self):
        guard = LoopGuard(max_hops=2)
        guard.check("ch1", "claude", AGENTS)
        guard.check("ch1", "codex", AGENTS)
        guard.check("ch1", "claude", AGENTS)  # triggers
        guard.reset("ch1")
        assert guard.is_paused("ch1") is False
        assert guard.hop_count("ch1") == 0

    def test_custom_max_hops(self):
        guard = LoopGuard(max_hops=1)
        assert guard.check("ch1", "claude", AGENTS) is True
        # 2nd hop triggers
        assert guard.check("ch1", "codex", AGENTS) is False

    def test_agent_check_case_insensitive(self):
        guard = LoopGuard(max_hops=2)
        assert guard.check("ch1", "Claude", AGENTS) is True
        assert guard.check("ch1", "CODEX", AGENTS) is True
        # 3rd triggers
        assert guard.check("ch1", "claude", AGENTS) is False


# --- MessageService integration tests ---


@pytest.fixture
def store(tmp_path):
    return MessageStore(data_dir=tmp_path)


@pytest.fixture
def service(store):
    return MessageService(store=store, known_agents=AGENTS, max_hops=3)


class TestLoopGuardIntegration:
    def test_agent_messages_create_deliveries_within_limit(self, service):
        """Agent messages with @mentions produce deliveries before guard triggers."""
        msg = service.send(text="@codex help", channel="general", sender="claude")
        assert msg.delivery is not None
        assert msg.delivery.target == "codex"

    def test_guard_triggers_after_max_hops(self, service):
        """After max_hops agent messages, deliveries are suppressed."""
        # 3 agent hops (within limit)
        service.send(text="@codex step1", channel="general", sender="claude")
        service.send(text="@claude step2", channel="general", sender="codex")
        service.send(text="@codex step3", channel="general", sender="claude")
        # 4th agent hop — guard triggers
        msg = service.send(text="@claude step4", channel="general", sender="codex")
        assert msg.delivery is None
        assert msg.deliveries == []

    def test_system_message_posted_on_trigger(self, service, store):
        """A system message is posted when the guard first triggers."""
        for i in range(3):
            sender = "claude" if i % 2 == 0 else "codex"
            service.send(text=f"@{'codex' if sender == 'claude' else 'claude'} msg{i}",
                         channel="general", sender=sender)
        # 4th hop triggers guard
        service.send(text="@claude again", channel="general", sender="codex")

        messages = store.list_by_channel("general")
        system_msgs = [m for m in messages if m.type == MessageType.SYSTEM]
        assert len(system_msgs) == 1
        assert "Loop guard activated" in system_msgs[0].text
        assert "4 consecutive" in system_msgs[0].text
        assert system_msgs[0].sender == "system"

    def test_subsequent_agent_messages_silently_blocked(self, service, store):
        """After guard triggers, further agent messages have no deliveries and no extra system messages."""
        for i in range(3):
            sender = "claude" if i % 2 == 0 else "codex"
            service.send(text=f"@{'codex' if sender == 'claude' else 'claude'} msg{i}",
                         channel="general", sender=sender)
        # Trigger guard
        service.send(text="@claude trigger", channel="general", sender="codex")
        # More agent messages
        msg5 = service.send(text="@codex more", channel="general", sender="claude")
        msg6 = service.send(text="@claude more", channel="general", sender="codex")
        assert msg5.delivery is None
        assert msg6.delivery is None

        # Only one system message total
        messages = store.list_by_channel("general")
        system_msgs = [m for m in messages if m.type == MessageType.SYSTEM]
        assert len(system_msgs) == 1

    def test_human_message_resets_guard(self, service):
        """Human message resets the guard so agents can route again."""
        for i in range(3):
            sender = "claude" if i % 2 == 0 else "codex"
            service.send(text=f"@{'codex' if sender == 'claude' else 'claude'} msg{i}",
                         channel="general", sender=sender)
        # Trigger guard
        service.send(text="@claude trigger", channel="general", sender="codex")
        # Human resets
        service.send(text="carry on", channel="general", sender="human")
        # Agent can route again
        msg = service.send(text="@codex resume", channel="general", sender="claude")
        assert msg.delivery is not None
        assert msg.delivery.target == "codex"

    def test_guard_per_channel(self, service):
        """Guard state is per-channel."""
        # Trigger guard in channel A
        for i in range(3):
            sender = "claude" if i % 2 == 0 else "codex"
            service.send(text=f"@{'codex' if sender == 'claude' else 'claude'} msg{i}",
                         channel="chan-a", sender=sender)
        service.send(text="@claude trigger", channel="chan-a", sender="codex")
        # Channel B is unaffected
        msg = service.send(text="@codex hello", channel="chan-b", sender="claude")
        assert msg.delivery is not None
        assert msg.delivery.target == "codex"

    def test_human_messages_never_blocked(self, service):
        """Human messages always go through even when guard is active."""
        for i in range(3):
            sender = "claude" if i % 2 == 0 else "codex"
            service.send(text=f"@{'codex' if sender == 'claude' else 'claude'} msg{i}",
                         channel="general", sender=sender)
        service.send(text="@claude trigger", channel="general", sender="codex")
        # Human message still works and creates deliveries
        msg = service.send(text="@claude can you help?", channel="general", sender="human")
        assert msg.delivery is not None
        assert msg.delivery.target == "claude"

    def test_agent_message_without_mention_still_stored(self, service, store):
        """Agent messages without @mentions are stored even during guard."""
        for i in range(3):
            sender = "claude" if i % 2 == 0 else "codex"
            service.send(text=f"@{'codex' if sender == 'claude' else 'claude'} msg{i}",
                         channel="general", sender=sender)
        service.send(text="@claude trigger", channel="general", sender="codex")
        msg = service.send(text="just thinking aloud", channel="general", sender="claude")
        assert msg.delivery is None
        # Still persisted
        persisted = store.get(msg.id)
        assert persisted is not None
        assert persisted.text == "just thinking aloud"
