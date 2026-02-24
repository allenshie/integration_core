"""Event dispatch engine interface."""
from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Dict, List, Type

from smart_workflow import TaskContext, TaskError


@dataclass
class EventDispatchResult:
    dispatched: int = 0
    failed: int = 0
    details: Dict[str, Any] | None = None


class BaseEventDispatchEngine(ABC):
    """Base interface for event dispatch engines."""

    def __init__(self, context: TaskContext | None = None) -> None:
        self._context = context

    @abstractmethod
    def dispatch(self, events: List[Dict[str, Any]], context: TaskContext) -> EventDispatchResult:
        """Dispatch events and return summary."""


class DefaultEventDispatchEngine(BaseEventDispatchEngine):
    """Fallback engine that only logs counts."""

    def dispatch(self, events: List[Dict[str, Any]], context: TaskContext) -> EventDispatchResult:
        count = len(events)
        for event in events:
            context.logger.info(
                "event dispatch: id=%s name=%s timestamp=%s event_type=%s",
                event.get("id"),
                event.get("name"),
                event.get("timestamp"),
                event.get("event_type"),
            )
        return EventDispatchResult(dispatched=count, failed=0)


def load_event_dispatch_engine(path: str) -> Type[BaseEventDispatchEngine]:
    if ":" in path:
        module_name, class_name = path.split(":", 1)
    elif "." in path:
        module_name, class_name = path.rsplit(".", 1)
    else:
        raise TaskError(f"無法解析 EventDispatch Engine 路徑：{path}")

    module = import_module(module_name)
    attr = getattr(module, class_name, None)
    if attr is None or not inspect.isclass(attr):
        raise TaskError(f"在模組 {module_name} 找不到 EventDispatch Engine {class_name}")
    if not issubclass(attr, BaseEventDispatchEngine):
        raise TaskError(f"{class_name} 必須繼承 BaseEventDispatchEngine")
    return attr
