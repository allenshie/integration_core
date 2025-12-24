"""Rule evaluation stage."""
from __future__ import annotations

from smart_workflow import BaseTask, TaskContext, TaskResult


class RuleEvaluationTask(BaseTask):
    name = "rule_evaluation"

    def __init__(self, context: TaskContext | None = None) -> None:
        self._detail = context.config.rules.detail if context and hasattr(context.config, "rules") else None

    def run(self, context: TaskContext) -> TaskResult:
        context.logger.info("完成節點：違規/作業規則判定%s", f" ({self._detail})" if self._detail else "")
        return TaskResult(status="rules_done")
