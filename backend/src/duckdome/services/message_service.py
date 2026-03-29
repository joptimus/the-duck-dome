from __future__ import annotations

import re
import time

from duckdome.models.message import Delivery, DeliveryState, Message
from duckdome.stores.message_store import MessageStore


class MessageService:
    def __init__(self, store: MessageStore, known_agents: list[str]) -> None:
        self._store = store
        self._known_agents = [a.lower() for a in known_agents]
        self._build_mention_regex()

    def _build_mention_regex(self) -> None:
        if not self._known_agents:
            self._mention_re = None
            return
        # Sort longest-first to avoid partial matches
        names = sorted(self._known_agents, key=len, reverse=True)
        escaped = "|".join(re.escape(n) for n in names)
        self._mention_re = re.compile(
            rf"(?<![a-zA-Z0-9_.])@({escaped})\b", re.IGNORECASE
        )

    def _parse_mentions(self, text: str) -> list[str]:
        if self._mention_re is None:
            return []
        matches = self._mention_re.findall(text)
        # Deduplicate, preserve order, normalize to lowercase
        seen: set[str] = set()
        result: list[str] = []
        for m in matches:
            name = m.lower()
            if name not in seen:
                seen.add(name)
                result.append(name)
        return result

    def send(self, text: str, channel: str, sender: str) -> Message:
        mentions = self._parse_mentions(text)

        delivery = None
        deliveries: list[Delivery] = []

        if len(mentions) == 1:
            delivery = Delivery(target=mentions[0])
        elif len(mentions) > 1:
            deliveries = [Delivery(target=name) for name in mentions]

        msg = Message(
            text=text,
            channel=channel,
            sender=sender,
            delivery=delivery,
            deliveries=deliveries,
        )
        self._store.add(msg)
        return msg

    def _get_delivery_for_agent(
        self, msg: Message, agent_name: str
    ) -> Delivery | None:
        agent = agent_name.lower()
        if msg.delivery and msg.delivery.target == agent:
            return msg.delivery
        for d in msg.deliveries:
            if d.target == agent:
                return d
        return None

    def mark_seen(self, msg_id: str, agent_name: str) -> Message | None:
        msg = self._store.get(msg_id)
        if msg is None:
            return None
        delivery = self._get_delivery_for_agent(msg, agent_name)
        if delivery is None:
            return None
        if delivery.state != DeliveryState.SENT:
            return msg
        delivery.state = DeliveryState.SEEN
        delivery.seen_at = time.time()
        return self._store.update(msg_id, msg)

    def mark_responded(
        self, msg_id: str, agent_name: str, response_id: str
    ) -> Message | None:
        msg = self._store.get(msg_id)
        if msg is None:
            return None
        delivery = self._get_delivery_for_agent(msg, agent_name)
        if delivery is None:
            return None
        if delivery.state not in (DeliveryState.SEEN, DeliveryState.TIMEOUT):
            return None
        delivery.state = DeliveryState.RESPONDED
        delivery.responded_at = time.time()
        delivery.response_id = response_id
        return self._store.update(msg_id, msg)

    def process_agent_read(
        self, agent_name: str, channel: str, read_up_to_id: str
    ) -> list[Message]:
        """Mark all sent messages targeted at agent as seen, up to read_up_to_id."""
        msgs = self._store.list_by_channel(channel)
        if not any(m.id == read_up_to_id for m in msgs):
            return []
        result: list[Message] = []
        for msg in msgs:
            d = self._get_delivery_for_agent(msg, agent_name)
            if d and d.state == DeliveryState.SENT:
                updated = self.mark_seen(msg.id, agent_name)
                if updated:
                    result.append(updated)
            if msg.id == read_up_to_id:
                break
        return result

    def process_agent_response(
        self, agent_name: str, channel: str, response_id: str
    ) -> list[Message]:
        """Mark all seen/timed-out messages targeted at agent as responded."""
        msgs = self._store.list_by_channel(channel)
        result: list[Message] = []
        for msg in msgs:
            d = self._get_delivery_for_agent(msg, agent_name)
            if d and d.state in (DeliveryState.SEEN, DeliveryState.TIMEOUT):
                updated = self.mark_responded(msg.id, agent_name, response_id)
                if updated:
                    result.append(updated)
        return result

    def list_messages(
        self, channel: str, after_id: str | None = None
    ) -> list[Message]:
        return self._store.list_by_channel(channel, after_id=after_id)

    def list_by_delivery_state(self, state: str) -> list[Message]:
        return self._store.list_by_delivery_state(state)

    def list_open_deliveries(self) -> list[Message]:
        sent = self._store.list_by_delivery_state("sent")
        seen = self._store.list_by_delivery_state("seen")
        seen_ids: set[str] = set()
        result: list[Message] = []
        for msg in sent + seen:
            if msg.id not in seen_ids:
                seen_ids.add(msg.id)
                result.append(msg)
        return result
