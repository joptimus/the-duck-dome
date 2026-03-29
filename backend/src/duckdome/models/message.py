from __future__ import annotations

import time
import uuid
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class DeliveryState(StrEnum):
    SENT = "sent"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    TIMEOUT = "timeout"


class Delivery(BaseModel):
    target: str
    state: DeliveryState = DeliveryState.SENT
    sent_at: float = Field(default_factory=time.time)
    delivered_at: float | None = None
    acknowledged_at: float | None = None
    response_id: str | None = None


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    channel: str
    sender: str
    timestamp: float = Field(default_factory=time.time)
    delivery: Delivery | None = None
    deliveries: list[Delivery] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_delivery_exclusivity(self) -> Message:
        if self.delivery is not None and self.deliveries:
            raise ValueError("Message cannot have both 'delivery' and 'deliveries'")
        return self
