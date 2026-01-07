"""Default selector that always runs the working pipeline."""
from __future__ import annotations

from integration.pipeline.selectors.base import BasePipelineSelector, PipelineSelection
from smart_workflow import TaskContext


class WorkingHoursSelector(BasePipelineSelector):
    """Core 預設 selector：永遠執行 working pipeline。"""

    def select(self, context: TaskContext) -> PipelineSelection:
        context.monitor.heartbeat(phase="working")
        return PipelineSelection(
            name="working",
            metadata={"phase": "working", "sleep": context.config.loop_interval_seconds},
        )
