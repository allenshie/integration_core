"""Scheduling utilities that determine pipeline phases."""
from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import import_module
from typing import Iterable, Type

from smart_workflow import TaskError

from integration.config.settings import ScheduleWindow


@dataclass(frozen=True)
class Phase:
    name: str
    is_working_hours: bool


class BaseSchedulerEngine(ABC):
    """Base scheduler engine interface."""

    def __init__(
        self,
        windows: Iterable[ScheduleWindow],
        tz: timezone,
        context=None,
    ) -> None:
        self._windows = list(windows)
        self._tz = tz
        self._context = context

    @abstractmethod
    def resolve_phase(self, now: datetime | None = None) -> Phase:
        """Return the current phase."""


class SinglePhaseSchedulerEngine(BaseSchedulerEngine):
    """Default scheduler: always return a single working phase."""

    def __init__(
        self,
        windows: Iterable[ScheduleWindow],
        tz: timezone,
        phase_name: str = "working",
        context=None,
    ) -> None:
        super().__init__(windows, tz, context=context)
        self._phase_name = phase_name

    def resolve_phase(self, now: datetime | None = None) -> Phase:
        _ = now
        return Phase(name=self._phase_name, is_working_hours=True)


class TimeWindowSchedulerEngine(BaseSchedulerEngine):
    """Scheduler based on configured working-hour windows."""

    def __init__(self, windows: Iterable[ScheduleWindow], tz: timezone, context=None) -> None:
        super().__init__(windows, tz, context=context)

    def resolve_phase(self, now: datetime | None = None) -> Phase:
        now = now or datetime.now(tz=self._tz)
        current_time = now.timetz().replace(tzinfo=None)
        for window in self._windows:
            if window.contains(current_time):
                return Phase(name="working", is_working_hours=True)
        return Phase(name="non_working", is_working_hours=False)


def load_scheduler_engine(path: str) -> Type[BaseSchedulerEngine]:
    if ":" in path:
        module_name, class_name = path.split(":", 1)
    elif "." in path:
        module_name, class_name = path.rsplit(".", 1)
    else:
        raise TaskError(f"無法解析 Scheduler Engine 路徑：{path}")
    module = import_module(module_name)
    attr = getattr(module, class_name, None)
    if attr is None or not inspect.isclass(attr):
        raise TaskError(f"在模組 {module_name} 找不到 Scheduler Engine {class_name}")
    if not issubclass(attr, BaseSchedulerEngine):
        raise TaskError(f"{class_name} 必須繼承 BaseSchedulerEngine")
    return attr


class PipelineScheduler:
    """Decides which pipeline should run via scheduler engine."""

    def __init__(
        self,
        windows: Iterable[ScheduleWindow],
        tz: timezone,
        engine_class: str | None = None,
        context=None,
    ) -> None:
        if engine_class:
            engine_cls = load_scheduler_engine(engine_class)
            try:
                self._engine = engine_cls(windows, tz, context=context)
            except TypeError:
                self._engine = engine_cls(windows, tz)
        else:
            self._engine = SinglePhaseSchedulerEngine(windows, tz, context=context)

    def current_phase(self, now: datetime | None = None) -> Phase:
        return self._engine.resolve_phase(now)
