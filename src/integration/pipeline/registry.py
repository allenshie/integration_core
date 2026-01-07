"""Registry utilities for dynamically registered pipelines."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from smart_workflow import BaseTask, TaskError


@dataclass
class PipelineEntry:
    task: BaseTask
    default_sleep: float | None = None


class PipelineRegistry:
    """Stores instantiated pipeline tasks keyed by symbolic names."""

    def __init__(self) -> None:
        self._pipelines: Dict[str, PipelineEntry] = {}

    def register(self, name: str, task: BaseTask, default_sleep: float | None = None) -> None:
        key = name.strip()
        if not key:
            raise TaskError("Pipeline 名稱不得為空")
        self._pipelines[key] = PipelineEntry(task=task, default_sleep=default_sleep)

    def get_entry(self, name: str) -> PipelineEntry:
        if name not in self._pipelines:
            known = ", ".join(sorted(self._pipelines.keys())) or "<none>"
            raise TaskError(f"找不到 pipeline '{name}'，可用名稱：{known}")
        return self._pipelines[name]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._pipelines.keys()))
