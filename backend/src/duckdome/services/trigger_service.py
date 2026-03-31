from __future__ import annotations

import time
from typing import TYPE_CHECKING

from duckdome.models.trigger import Trigger, TriggerStatus
from duckdome.models.channel import AgentInstance
from duckdome.stores.trigger_store import TriggerStore
from duckdome.stores.base import BaseChannelStore

if TYPE_CHECKING:
    from duckdome.services.message_service import MessageService
    from duckdome.ws.manager import ConnectionManager


class TriggerService:
    def __init__(
        self,
        trigger_store: TriggerStore,
        channel_store: BaseChannelStore,
        ws_manager: ConnectionManager | None = None,
        message_service: MessageService | None = None,
    ) -> None:
        self._triggers = trigger_store
        self._channels = channel_store
        self._ws_manager = ws_manager
        self._messages = message_service

    def _broadcast(self, event: dict) -> None:
        """Fire-and-forget broadcast to WebSocket clients (if manager is set)."""
        if self._ws_manager is None:
            return
        self._ws_manager.broadcast_sync(event)

    def set_message_service(self, message_service: MessageService) -> None:
        self._messages = message_service

    def _post_system_event(self, *, channel_id: str, subtype: str, agent_type: str, text: str) -> None:
        if self._messages is None:
            return
        self._messages.post_system_event(
            channel=channel_id,
            subtype=subtype,
            agent=agent_type,
            text=text,
        )

    # --- Trigger lifecycle ---

    def create_trigger(
        self,
        channel_id: str,
        target_agent_type: str,
        source_message_id: str,
    ) -> Trigger:
        if self._channels.get_channel(channel_id) is None:
            raise ValueError(f"Channel not found: {channel_id}")
        agent_id = f"{channel_id}:{target_agent_type}"
        if self._channels.get_agent(agent_id) is None:
            raise ValueError(
                f"Agent {target_agent_type} not registered in channel {channel_id}"
            )
        trigger = Trigger(
            channel_id=channel_id,
            target_agent_type=target_agent_type,
            source_message_id=source_message_id,
        )
        return self._triggers.add(trigger)

    def claim_trigger(
        self, channel_id: str, agent_type: str
    ) -> Trigger | None:
        agent_id = f"{channel_id}:{agent_type}"
        agent = self._channels.get_agent(agent_id)
        if agent is None or agent.status != "idle":
            return None
        pending = self._triggers.list_by_agent(agent_id, status="pending")
        if not pending:
            return None
        trigger = pending[0]
        trigger.status = TriggerStatus.CLAIMED
        trigger.claimed_at = time.time()
        self._triggers.update(trigger.id, trigger)

        # Update agent status to working
        agent.status = "working"
        agent.current_task = trigger.source_message_id
        self._channels.update_agent(agent_id, agent)

        self._broadcast({
            "type": "trigger_state_change",
            "trigger_id": trigger.id,
            "state": trigger.status.value,
        })
        self._broadcast({
            "type": "agent_status_change",
            "agent_id": agent_id,
            "status": agent.status,
        })

        return trigger

    def complete_trigger(self, trigger_id: str) -> Trigger | None:
        trigger = self._triggers.get(trigger_id)
        if trigger is None:
            return None
        if trigger.status != TriggerStatus.CLAIMED:
            return None
        trigger.status = TriggerStatus.COMPLETED
        trigger.completed_at = time.time()
        self._triggers.update(trigger_id, trigger)

        # Update agent status to idle
        agent = self._channels.get_agent(trigger.target_agent_instance_id)
        if agent:
            agent.status = "idle"
            agent.last_response = time.time()
            agent.current_task = None
            self._channels.update_agent(agent.id, agent)
            self._broadcast({
                "type": "agent_status_change",
                "agent_id": agent.id,
                "status": agent.status,
            })

        self._broadcast({
            "type": "trigger_state_change",
            "trigger_id": trigger.id,
            "state": trigger.status.value,
        })

        return trigger

    def fail_trigger(self, trigger_id: str, error: str) -> Trigger | None:
        trigger = self._triggers.get(trigger_id)
        if trigger is None:
            return None
        if trigger.status != TriggerStatus.CLAIMED:
            return None
        trigger.status = TriggerStatus.FAILED
        trigger.completed_at = time.time()
        trigger.last_error = error
        self._triggers.update(trigger_id, trigger)

        # Update agent status
        agent = self._channels.get_agent(trigger.target_agent_instance_id)
        if agent:
            agent.status = "idle"
            agent.current_task = None
            agent.last_error = error
            self._channels.update_agent(agent.id, agent)
            self._broadcast({
                "type": "agent_status_change",
                "agent_id": agent.id,
                "status": agent.status,
            })

        self._broadcast({
            "type": "trigger_state_change",
            "trigger_id": trigger.id,
            "state": trigger.status.value,
        })

        return trigger

    def list_triggers(
        self, channel_id: str, status: str | None = None
    ) -> list[Trigger]:
        return self._triggers.list_by_channel(channel_id, status=status)

    def get_trigger(self, trigger_id: str) -> Trigger | None:
        return self._triggers.get(trigger_id)

    # --- Agent runtime ---

    def register_agent(
        self, channel_id: str, agent_type: str
    ) -> AgentInstance:
        if self._channels.get_channel(channel_id) is None:
            raise ValueError(f"Channel not found: {channel_id}")
        agent_id = f"{channel_id}:{agent_type}"
        existing = self._channels.get_agent(agent_id)
        if existing:
            was_offline = existing.status == "offline"
            existing.status = "idle"
            existing.last_heartbeat = time.time()
            existing.last_error = None
            existing.current_task = None
            self._channels.update_agent(agent_id, existing)
            if was_offline:
                self._post_system_event(
                    channel_id=channel_id,
                    subtype="join",
                    agent_type=agent_type,
                    text="joined the channel",
                )
            return existing
        agent = AgentInstance(
            channel_id=channel_id,
            agent_type=agent_type,
            status="idle",
            last_heartbeat=time.time(),
        )
        added = self._channels.add_agent(agent)
        self._post_system_event(
            channel_id=channel_id,
            subtype="join",
            agent_type=agent_type,
            text="joined the channel",
        )
        return added

    def heartbeat(
        self, channel_id: str, agent_type: str
    ) -> AgentInstance | None:
        agent_id = f"{channel_id}:{agent_type}"
        agent = self._channels.get_agent(agent_id)
        if agent is None:
            return None
        agent.last_heartbeat = time.time()
        updated = self._channels.update_agent(agent_id, agent)
        if updated:
            self._broadcast({
                "type": "agent_status_change",
                "agent_id": agent_id,
                "status": updated.status,
            })
        return updated

    def deregister_agent(
        self, channel_id: str, agent_type: str
    ) -> AgentInstance | None:
        agent_id = f"{channel_id}:{agent_type}"
        agent = self._channels.get_agent(agent_id)
        if agent is None:
            return None
        agent.status = "offline"
        agent.current_task = None
        updated = self._channels.update_agent(agent_id, agent)
        if updated is not None:
            self._post_system_event(
                channel_id=channel_id,
                subtype="leave",
                agent_type=agent_type,
                text="left the channel",
            )
        return updated
