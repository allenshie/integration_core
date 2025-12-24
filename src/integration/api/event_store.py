"""In-memory event store for edge inference results."""
from __future__ import annotations

import threading
from collections import deque
from typing import Any, Deque, Dict, List


class EdgeEventStore:
    """Thread-safe store holding latest edge events."""

    def __init__(self, max_events: int = 2000) -> None:
        self._events: Deque[Dict[str, Any]] = deque(maxlen=max_events)
        self._lock = threading.Lock()

    def add_event(self, event: Dict[str, Any]) -> None:
        with self._lock:
            self._events.append(event)

    def pop_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            events = list(self._events)
            self._events.clear()
            return events
