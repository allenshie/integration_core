"""Utilities for queueing workflow events before dispatch."""
from __future__ import annotations

from typing import Any, Dict, List

from smart_workflow import TaskContext

EVENT_QUEUE_RESOURCE = "event_queue"


def get_event_queue(context: TaskContext) -> List[Dict[str, Any]]:
    """Return the mutable event queue stored on the context."""
    queue = context.get_resource(EVENT_QUEUE_RESOURCE)
    if queue is None:
        queue = []
        context.set_resource(EVENT_QUEUE_RESOURCE, queue)
    return queue


def enqueue_event(context: TaskContext, event: Dict[str, Any]) -> None:
    """Append an event payload to the queue."""
    queue = get_event_queue(context)
    queue.append(event)
