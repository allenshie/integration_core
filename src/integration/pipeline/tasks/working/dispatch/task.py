"""Dispatch queued events to the configured engine."""
from __future__ import annotations

from typing import Iterable

from smart_workflow import BaseTask, TaskContext, TaskResult

from integration.pipeline.events import EVENT_QUEUE_RESOURCE, get_event_queue
from integration.pipeline.tasks.working.dispatch.engine import (
    BaseEventDispatchEngine,
    DefaultEventDispatchEngine,
    load_event_dispatch_engine,
)


class EventDispatchTask(BaseTask):
    name = "event_dispatch"

    def __init__(self, context: TaskContext | None = None) -> None:
        cfg = getattr(context.config, "event_dispatch", None) if context else None
        engine_path = getattr(cfg, "engine_class", None) if cfg else None
        self._engine = self._init_engine(engine_path, context)

    def run(self, context: TaskContext) -> TaskResult:
        queue = get_event_queue(context)
        if not queue:
            context.logger.debug("Event queue empty，略過派送")
            return TaskResult(status="event_dispatch_idle")

        events = list(queue)
        queue.clear()
        self._engine.dispatch(context, events)
        context.logger.info("已派送 %d 筆事件", len(events))
        return TaskResult(status="event_dispatch_done", payload={"dispatched_events": len(events)})

    def _init_engine(
        self,
        engine_path: str | None,
        context: TaskContext | None,
    ) -> BaseEventDispatchEngine:
        if not engine_path:
            return DefaultEventDispatchEngine(context=context)
        engine_cls = load_event_dispatch_engine(engine_path)
        try:
            return engine_cls(context=context)
        except TypeError:
            return engine_cls()
