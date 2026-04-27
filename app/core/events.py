from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True)
class DomainEvent:
    event_type: str
    payload: dict[str, Any]
    tenant_id: UUID | None = None
    correlation_id: str | None = None
    event_id: UUID = field(default_factory=uuid4)


EventHandler = Callable[[DomainEvent], Awaitable[None]]


class EventDispatcher:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}

    def register(self, event_type: str, handler: EventHandler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    async def publish(self, event: DomainEvent) -> None:
        for handler in self._handlers.get(event.event_type, []):
            await handler(event)


event_dispatcher = EventDispatcher()
