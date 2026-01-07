"""Phase controller task that delegates to registered pipelines via selector."""
from __future__ import annotations

from smart_workflow import BaseTask, TaskContext, TaskResult

from integration.pipeline.registry import PipelineRegistry
from integration.pipeline.selectors.base import BasePipelineSelector


class PhaseTask(BaseTask):
    name = "phase_controller"

    def run(self, context: TaskContext) -> TaskResult:
        registry: PipelineRegistry = context.require_resource("pipeline_registry")
        selector: BasePipelineSelector = context.require_resource("pipeline_selector")

        selection = selector.select(context)
        entry = registry.get_entry(selection.name)
        result = entry.task.execute(context)

        payload = {}
        if selection.metadata:
            payload.update(selection.metadata)
        if result and result.payload:
            payload.update(result.payload)

        if "sleep" not in payload and entry.default_sleep is not None:
            payload["sleep"] = entry.default_sleep

        status = result.status if result else f"{selection.name}_completed"
        return TaskResult(status=status, payload=payload or None)
