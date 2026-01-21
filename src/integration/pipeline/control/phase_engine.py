"""Phase engine interface and default implementations."""
from __future__ import annotations

import inspect
import os
from datetime import datetime
from abc import ABC, abstractmethod
from importlib import import_module
from typing import Type

from smart_workflow import TaskContext, TaskError

from integration.pipeline.control.scheduler import Phase


class BasePhaseEngine(ABC):
    """Resolve the current phase for the integration pipeline."""

    def __init__(self, context: TaskContext | None = None) -> None:
        self._context = context

    @abstractmethod
    def resolve(self, context: TaskContext) -> Phase:
        """Return the phase for the current cycle."""


class TimeBasedPhaseEngine(BasePhaseEngine):
    """Default phase engine based on configured schedule windows."""

    def resolve(self, context: TaskContext) -> Phase:
        scheduler = context.require_resource("scheduler")
        return scheduler.current_phase()


class DebouncedPhaseEngine(BasePhaseEngine):
    """Switch phase only after the candidate phase stays stable for a window."""

    def __init__(self, context: TaskContext | None = None) -> None:
        super().__init__(context)
        self._stable_phase: Phase | None = None
        self._pending_phase: Phase | None = None
        self._pending_since: datetime | None = None
        self._stable_seconds = int(os.getenv("PHASE_STABLE_SECONDS", "180"))
        self._stale_seconds = int(os.getenv("EDGE_EVENT_STALE_SECONDS", "0"))
        self._stale_mode = os.getenv("EDGE_EVENT_STALE_MODE", "freeze").strip().lower()
        self._unknown_phase = os.getenv("EDGE_EVENT_UNKNOWN_PHASE", "unknown").strip() or "unknown"

    def resolve(self, context: TaskContext) -> Phase:
        scheduler = context.require_resource("scheduler")
        candidate = scheduler.current_phase(self._latest_event_time(context))
        latest_event = self._latest_event_time(context)
        if self._is_stale(latest_event):
            if self._stale_mode == "unknown":
                return Phase(name=self._unknown_phase, is_working_hours=False)
            if self._stable_phase is not None:
                return self._stable_phase

        if self._stable_phase is None:
            self._stable_phase = candidate
            return candidate

        if candidate.name == self._stable_phase.name:
            self._pending_phase = None
            self._pending_since = None
            return self._stable_phase

        if self._pending_phase is None or candidate.name != self._pending_phase.name:
            self._pending_phase = candidate
            self._pending_since = self._latest_event_time(context) or self._now()
            return self._stable_phase

        if self._pending_since is None:
            self._pending_since = self._latest_event_time(context) or self._now()
            return self._stable_phase

        if self._seconds_since(self._pending_since) >= self._stable_seconds:
            self._stable_phase = candidate
            self._pending_phase = None
            self._pending_since = None
        return self._stable_phase

    def _latest_event_time(self, context: TaskContext) -> datetime | None:
        events = context.get_resource("edge_events") or []
        timestamps = [event.get("timestamp") for event in events if event.get("timestamp")]
        if not timestamps:
            return None
        return max(timestamps)

    def _seconds_since(self, since: datetime) -> float:
        return (self._now(since.tzinfo) - since).total_seconds()

    def _now(self, tzinfo=None) -> datetime:
        return datetime.now(tz=tzinfo)

    def _is_stale(self, latest_event: datetime | None) -> bool:
        if self._stale_seconds <= 0 or latest_event is None:
            return False
        return (self._now(latest_event.tzinfo) - latest_event).total_seconds() >= self._stale_seconds


def load_phase_engine(path: str) -> Type[BasePhaseEngine]:
    if ":" in path:
        module_name, class_name = path.split(":", 1)
    elif "." in path:
        module_name, class_name = path.rsplit(".", 1)
    else:
        raise TaskError(f"無法解析 Phase Engine 路徑：{path}")

    module = import_module(module_name)
    attr = getattr(module, class_name, None)
    if attr is None or not inspect.isclass(attr):
        raise TaskError(f"在模組 {module_name} 找不到 Phase Engine {class_name}")
    if not issubclass(attr, BasePhaseEngine):
        raise TaskError(f"{class_name} 必須繼承 BasePhaseEngine")
    return attr
