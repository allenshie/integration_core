"""Phase controller task switching working/non-working pipelines."""
from __future__ import annotations

from datetime import date

from integration.pipeline.scheduler import PipelineScheduler
from smart_workflow import BaseTask, TaskContext, TaskResult
from integration.storage.state import ZoneStateRepository


class PhaseTask(BaseTask):
    name = "phase_controller"

    def run(self, context: TaskContext) -> TaskResult:
        scheduler: PipelineScheduler = context.require_resource("scheduler")
        zone_repo: ZoneStateRepository = context.require_resource("zone_repo")
        working_pipeline = context.require_resource("working_pipeline")
        non_working_task = context.require_resource("non_working_task")

        phase = scheduler.current_phase()
        context.monitor.heartbeat(phase=phase.name)

        if phase.is_working_hours:
            working_pipeline.execute(context)
            return TaskResult(status="working_phase", payload={"phase": phase.name})

        today = date.today()
        if zone_repo.is_zone_state_updated(today):
            context.logger.info("非工作時段：今日已更新，暫停 %ss", context.config.non_working_idle_seconds)
            return TaskResult(
                status="non_working_idle",
                payload={
                    "phase": phase.name,
                    "sleep": context.config.non_working_idle_seconds,
                },
            )

        non_working_task.execute(context)
        zone_repo.mark_zone_state_updated(today)
        return TaskResult(status="non_working_phase", payload={"phase": phase.name})
