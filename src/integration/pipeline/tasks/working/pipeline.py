"""Working hours pipeline composed of multiple stages."""
from __future__ import annotations

from typing import Iterable, List

from smart_workflow import BaseTask, TaskContext, TaskResult


class WorkingPipelineTask(BaseTask):
    name = "working_pipeline"

    def __init__(self, nodes: Iterable[BaseTask]) -> None:
        self.pipeline_nodes: List[BaseTask] = list(nodes)

    def run(self, context: TaskContext) -> TaskResult:
        for node in self.pipeline_nodes:
            node.execute(context)
        context.logger.info("工作時段流程完成")
        return TaskResult(status="working_pipeline_done")
