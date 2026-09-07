"""In-memory event + reply store. M1 does not need a database."""

from __future__ import annotations

import threading
from collections import OrderedDict

from pair_bridge.models import AssistantReply, StoredEvent


class EventStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: OrderedDict[str, StoredEvent] = OrderedDict()
        self._replies: OrderedDict[str, AssistantReply] = OrderedDict()

    def put_event(self, event: StoredEvent) -> None:
        with self._lock:
            self._events[event.context_id] = event

    def get_event(self, context_id: str) -> StoredEvent | None:
        with self._lock:
            return self._events.get(context_id)

    def list_events(self) -> list[StoredEvent]:
        with self._lock:
            return list(self._events.values())

    def put_reply(self, reply: AssistantReply) -> None:
        with self._lock:
            self._replies[reply.reply_id] = reply

    def latest_reply(self, context_id: str | None = None) -> AssistantReply | None:
        with self._lock:
            if context_id is None:
                if not self._replies:
                    return None
                return next(reversed(self._replies.values()))
            for reply in reversed(self._replies.values()):
                if reply.context_id == context_id:
                    return reply
            return None
