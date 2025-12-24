"""Non-working hours tasks."""
from __future__ import annotations

from smart_workflow import BaseTask, TaskContext, TaskResult


class NonWorkingUpdateTask(BaseTask):
    name = "non_working_update"

    def __init__(self, context: TaskContext | None = None) -> None:
        self._idle_seconds = context.config.non_working_idle_seconds if context else None

    def run(self, context: TaskContext) -> TaskResult:
        context.logger.info("非工作時段：執行貨物區域更新（模擬）")
        return TaskResult(status="non_working_update_done", payload={"sleep": self._idle_seconds})
