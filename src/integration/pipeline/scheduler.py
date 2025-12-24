"""Scheduling utilities that determine working/non-working phases."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from integration.config.settings import ScheduleWindow


@dataclass(frozen=True)
class Phase:
    name: str
    is_working_hours: bool


class PipelineScheduler:
    """Decides which pipeline should run based on configured windows."""

    def __init__(self, windows: Iterable[ScheduleWindow], tz: timezone) -> None:
        self._windows = list(windows)
        self._tz = tz

    def current_phase(self, now: datetime | None = None) -> Phase:
        now = now or datetime.now(tz=self._tz)
        current_time = now.timetz().replace(tzinfo=None)

        for window in self._windows:
            if window.contains(current_time):
                return Phase(name="working", is_working_hours=True)
        return Phase(name="non_working", is_working_hours=False)
