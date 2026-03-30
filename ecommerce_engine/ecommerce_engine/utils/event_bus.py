from datetime import datetime
from typing import List, Dict, Any, Callable


class Event:
    def __init__(self, event_type: str, data: Dict[str, Any]):
        self.event_type = event_type
        self.data = data
        self.timestamp = datetime.now()

    def __repr__(self):
        ts = self.timestamp.strftime("%H:%M:%S")
        return f"[{ts}] {self.event_type} -> {self.data}"


class EventBus:
    """
    Simple in-memory event queue.
    Supports publish/subscribe pattern.
    Events must execute in order; a failure stops subsequent events.
    """

    def __init__(self):
        self._queue: List[Event] = []
        self._handlers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def publish(self, event_type: str, data: Dict[str, Any]):
        event = Event(event_type, data)
        self._queue.append(event)

        # fire handlers in order, stop if one fails
        for handler in self._handlers.get(event_type, []):
            try:
                handler(event)
            except Exception as e:
                print(f"  [EventBus] Handler failed for {event_type}: {e}")
                break

        return event

    def get_all(self) -> List[Event]:
        return list(self._queue)

    def get_recent(self, n: int = 20) -> List[Event]:
        return list(self._queue[-n:])


# shared instance
event_bus = EventBus()
