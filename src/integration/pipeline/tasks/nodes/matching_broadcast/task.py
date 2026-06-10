"""Task that publishes MC-MOT matching results for downstream consumers."""
from __future__ import annotations

from typing import Any, Iterable

from smart_workflow import TaskContext, TaskResult

from integration.pipeline.tasks.base import QuietTaskBase
from integration.pipeline.tasks.summary import MATCHING_BROADCAST_STATS_RESOURCE, store_stage_stats

from .constants import MATCHING_BROADCAST_ROUTE
from .schema import MatchingBroadcastPayload


class MatchingBroadcastTask(QuietTaskBase):
    """Broadcast the current matching table as a shared payload."""

    name = "matching_broadcast"

    def __init__(self, context: TaskContext | None = None) -> None:
        _ = context

    def run(self, context: TaskContext) -> TaskResult:
        tracked_objects = list(context.get_resource("mc_mot_tracked") or [])
        broadcast_cfg = getattr(context.config, "matching_broadcast", None)
        enabled = bool(getattr(broadcast_cfg, "enabled", False)) if broadcast_cfg is not None else False

        if not enabled:
            store_stage_stats(
                context,
                MATCHING_BROADCAST_STATS_RESOURCE,
                {
                    "dispatched": 0,
                    "skipped": 1,
                    "failed": 0,
                },
            )
            context.logger.debug("matching broadcast disabled, skip %d tracked objects", len(tracked_objects))
            return TaskResult(
                status="matching_broadcast_skipped",
                payload={"reason": "disabled", "tracked": len(tracked_objects)},
            )

        if not tracked_objects:
            store_stage_stats(
                context,
                MATCHING_BROADCAST_STATS_RESOURCE,
                {
                    "dispatched": 0,
                    "skipped": 1,
                    "failed": 0,
                },
            )
            context.logger.debug("matching broadcast skipped: no tracked objects")
            return TaskResult(status="matching_broadcast_skipped", payload={"reason": "no_tracked_objects"})

        payload = MatchingBroadcastPayload.from_tracked_objects(tracked_objects).to_dict()
        if not payload.get("camera_matches"):
            store_stage_stats(
                context,
                MATCHING_BROADCAST_STATS_RESOURCE,
                {
                    "dispatched": 0,
                    "skipped": 1,
                    "failed": 0,
                },
            )
            context.logger.debug("matching broadcast skipped: no valid camera matches")
            return TaskResult(status="matching_broadcast_skipped", payload={"reason": "no_valid_tracks"})

        messaging = context.get_resource("messaging_client")
        if messaging is None:
            store_stage_stats(
                context,
                MATCHING_BROADCAST_STATS_RESOURCE,
                {
                    "dispatched": 0,
                    "skipped": 1,
                    "failed": 0,
                },
            )
            context.logger.warning("matching broadcast skipped: messaging_client not ready")
            return TaskResult(status="matching_broadcast_skipped", payload={"reason": "messaging_client_not_ready"})

        try:
            published = messaging.publish(MATCHING_BROADCAST_ROUTE, payload)
        except Exception as exc:  # pylint: disable=broad-except
            store_stage_stats(
                context,
                MATCHING_BROADCAST_STATS_RESOURCE,
                {
                    "dispatched": 0,
                    "skipped": 0,
                    "failed": 1,
                },
            )
            context.logger.warning("matching broadcast failed: %s", exc)
            return TaskResult(
                status="matching_broadcast_failed",
                payload={"reason": "publish_exception", "error": str(exc)},
            )

        if not published:
            store_stage_stats(
                context,
                MATCHING_BROADCAST_STATS_RESOURCE,
                {
                    "dispatched": 0,
                    "skipped": 0,
                    "failed": 1,
                },
            )
            context.logger.warning("matching broadcast failed: backend rejected publish")
            return TaskResult(status="matching_broadcast_failed", payload={"reason": "publish_rejected"})

        store_stage_stats(
            context,
            MATCHING_BROADCAST_STATS_RESOURCE,
            {
                "dispatched": 1,
                "skipped": 0,
                "failed": 0,
            },
        )
        context.logger.debug(
            "matching broadcast completed: cameras=%d tracked=%d",
            len(payload.get("camera_matches") or {}),
            len(tracked_objects),
        )
        return TaskResult(
            status="matching_broadcast_done",
            payload={
                "dispatched": 1,
                "cameras": len(payload.get("camera_matches") or {}),
                "tracked": len(tracked_objects),
            },
        )
