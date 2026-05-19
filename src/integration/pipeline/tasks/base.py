"""Task helpers for integration pipeline nodes."""
from __future__ import annotations

from smart_workflow import BaseTask, TaskContext, TaskError, TaskResult


class QuietTaskBase(BaseTask):
    """Base task that skips the default per-run start INFO log."""

    def execute(self, context: TaskContext) -> TaskResult:
        try:
            result = self.run(context)
        except TaskError as exc:
            context.report_failure(self.name, detail=str(exc))
            raise
        except Exception as exc:  # noqa: BLE001
            context.report_failure(self.name, detail=str(exc))
            raise

        result = result or TaskResult()
        context.report_success(self.name)
        return result
