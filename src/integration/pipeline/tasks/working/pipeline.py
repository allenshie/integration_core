"""Working hours pipeline composed of multiple stages."""
from __future__ import annotations

from typing import List

from smart_workflow import BaseTask, TaskContext, TaskResult

from integration.pipeline.tasks.working.ingestion.task import IngestionTask
from integration.pipeline.tasks.working.mc_mot.task import MCMOTTask
from integration.pipeline.tasks.working.formatting.task import FormatConversionTask
from integration.pipeline.tasks.working.rules.task import RuleEvaluationTask
from integration.pipeline.tasks.working.dispatch.task import EventDispatchTask


class WorkingPipelineTask(BaseTask):
    name = "working_pipeline"

    def __init__(self, context: TaskContext) -> None:
        self.pipeline_nodes: List[BaseTask] = self._build_nodes(context)

    def run(self, context: TaskContext) -> TaskResult:
        for node in self.pipeline_nodes:
            node.execute(context)
        context.logger.info("工作時段流程完成")
        return TaskResult(status="working_pipeline_done")

    def _build_nodes(self, context: TaskContext) -> List[BaseTask]:
        nodes: List[BaseTask] = [
            IngestionTask(context),
            MCMOTTask(context),
        ]
        cfg = getattr(context.config, "format_task", None)
        enabled = getattr(cfg, "enabled", True)
        if enabled:
            nodes.append(FormatConversionTask(context))
        nodes.append(RuleEvaluationTask(context))
        nodes.append(EventDispatchTask(context))
        return nodes
