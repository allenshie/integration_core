"""Event dispatch stage."""
from __future__ import annotations

from typing import Any, Dict, List

from smart_workflow import BaseTask, TaskContext, TaskResult, TaskError

from .engine import (
    BaseEventDispatchEngine,
    DefaultEventDispatchEngine,
    EventDispatchResult,
    load_event_dispatch_engine,
)


class EventDispatchTask(BaseTask):
    name = "event_dispatch"

    def __init__(self, context: TaskContext | None = None) -> None:
        self._engine: BaseEventDispatchEngine | None = None

    def run(self, context: TaskContext) -> TaskResult:
        if self._engine is None:
            cfg = getattr(context.config, "event_dispatch", None)
            self._engine = self._init_engine(cfg, context)
        events: List[Dict[str, Any]] = context.get_resource("rule_events") or []
        if not isinstance(events, list):
            raise TaskError("rule_events 必須是 list")
        for event in events:
            if not isinstance(event, dict):
                raise TaskError("rule_events 必須是 dict list")
            for key in ("id", "name", "timestamp", "event_type"):
                if key not in event:
                    raise TaskError(f"event missing field: {key}")

        result = self._engine.dispatch(events, context)
        payload = {"dispatched": result.dispatched, "failed": result.failed}
        if result.details:
            payload["details"] = result.details
        return TaskResult(status="event_dispatch_done", payload=payload)

    def _init_engine(self, cfg, context: TaskContext | None) -> BaseEventDispatchEngine:
        engine_path = getattr(cfg, "engine_class", None) if cfg else None
        if not engine_path:
            return DefaultEventDispatchEngine(context=context)
        try:
            engine_cls = load_event_dispatch_engine(engine_path)
        except Exception as exc:  # pylint: disable=broad-except
            raise TaskError(f"無法載入事件派送 Engine：{engine_path}") from exc

        try:
            return engine_cls(context=context)
        except TypeError:
            try:
                return engine_cls()
            except TypeError as exc:  # pragma: no cover
                raise TaskError(f"事件派送 Engine {engine_path} 無法初始化") from exc
