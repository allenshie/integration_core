"""Task that publishes MC-MOT matching results for downstream consumers."""
from __future__ import annotations

from smart_workflow import TaskContext, TaskResult

from integration.pipeline.tasks.base import QuietTaskBase
from integration.pipeline.tasks.summary import MATCHING_BROADCAST_STATS_RESOURCE, store_stage_stats

from .engine import BaseMatchingBroadcastEngine, DefaultMatchingBroadcastEngine, MatchingBroadcastResult


class MatchingBroadcastTask(QuietTaskBase):
    """Publish the current matching table as a shared payload."""

    name = "matching_broadcast"

    def __init__(self, context: TaskContext | None = None) -> None:
        self._engine: BaseMatchingBroadcastEngine | None = None

    def run(self, context: TaskContext) -> TaskResult:
        if self._engine is None:
            self._engine = self._init_engine(context)

        tracked_objects = list(context.get_resource("mc_mot_tracked") or [])
        result = self._engine.broadcast(tracked_objects, context)
        self._store_stage_stats(context, result)
        return self._build_task_result(result)

    def _init_engine(self, context: TaskContext | None) -> BaseMatchingBroadcastEngine:
        _ = context
        return DefaultMatchingBroadcastEngine(context=context)

    @staticmethod
    def _store_stage_stats(context: TaskContext, result: MatchingBroadcastResult) -> None:
        store_stage_stats(
            context,
            MATCHING_BROADCAST_STATS_RESOURCE,
            {
                "dispatched": result.dispatched,
                "skipped": result.skipped,
                "failed": result.failed,
            },
        )

    @staticmethod
    def _build_task_result(result: MatchingBroadcastResult) -> TaskResult:
        if result.dispatched > 0:
            status = "matching_broadcast_done"
        elif result.failed > 0:
            status = "matching_broadcast_failed"
        else:
            status = "matching_broadcast_skipped"

        payload = result.task_payload or {}
        if result.reason and "reason" not in payload:
            payload = dict(payload)
            payload["reason"] = result.reason
        return TaskResult(status=status, payload=payload)
