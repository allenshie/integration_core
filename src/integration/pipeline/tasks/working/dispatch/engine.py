"""Event dispatch engine interface and default logging implementation."""
from __future__ import annotations

import inspect
import json
from abc import ABC, abstractmethod
from importlib import import_module
from typing import Any, Dict, Iterable, Type

from smart_workflow import TaskContext, TaskError


class BaseEventDispatchEngine(ABC):
    """Base class for project-specific event delivery."""

    def __init__(self, context: TaskContext | None = None) -> None:
        self._context = context

    @abstractmethod
    def dispatch(self, context: TaskContext, events: Iterable[Dict[str, Any]]) -> None:
        """Send events to external services."""


class DefaultEventDispatchEngine(BaseEventDispatchEngine):
    """Logging-only fallback engine."""

    def dispatch(self, context: TaskContext, events: Iterable[Dict[str, Any]]) -> None:
        for event in events:
            handlers = event.get("handlers") or ["internal_db"]
            for handler in handlers:
                context.logger.info(
                    "[DefaultDispatch][%s] %s",
                    handler,
                    json.dumps(event, ensure_ascii=False),
                )


def load_event_dispatch_engine(path: str) -> Type[BaseEventDispatchEngine]:
    if ":" in path:
        module_name, class_name = path.split(":", 1)
    elif "." in path:
        module_name, class_name = path.rsplit(".", 1)
    else:
        raise TaskError(f"無法解析 Event Dispatch Engine 路徑：{path}")

    module = import_module(module_name)
    attr = getattr(module, class_name, None)
    if attr is None or not inspect.isclass(attr):
        raise TaskError(f"在模組 {module_name} 找不到 Event Dispatch Engine {class_name}")
    if not issubclass(attr, BaseEventDispatchEngine):
        raise TaskError(f"{class_name} 必須繼承 BaseEventDispatchEngine")
    return attr
