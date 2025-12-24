"""Ingestion stage task."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from smart_workflow import BaseTask, TaskContext, TaskResult


class IngestionTask(BaseTask):
    name = "ingestion"

    def __init__(self, context: TaskContext | None = None) -> None:
        self._max_age_seconds = context.config.edge_event_max_age_seconds if context else None

    def run(self, context: TaskContext) -> TaskResult:
        store = context.require_resource("edge_event_store")
        raw_events = store.pop_all()
        max_age_seconds = self._max_age_seconds or context.config.edge_event_max_age_seconds
        max_age = timedelta(seconds=max_age_seconds)
        now = datetime.now(timezone.utc)

        latest_events: Dict[str, Dict[str, Any]] = {}
        dropped = 0
        for item in raw_events:
            parsed = self._normalize_event(item, now, max_age)
            if parsed is None:
                dropped += 1
                continue
            camera_id = parsed["camera_id"]
            current = latest_events.get(camera_id)
            if current is None or parsed["timestamp"] > current["timestamp"]:
                latest_events[camera_id] = parsed

        deduped_events = list(latest_events.values())
        context.set_resource("edge_events", deduped_events)
        context.logger.info(
            "匯入 %d 台相機的最新事件（原始 %d 筆，丟棄 %d 筆）",
            len(deduped_events),
            len(raw_events),
            dropped,
        )
        return TaskResult(
            status="ingestion_done",
            payload={
                "events": len(deduped_events),
                "raw": len(raw_events),
                "dropped": dropped,
            },
        )

    def _normalize_event(
        self,
        item: Dict[str, Any],
        now: datetime,
        max_age: timedelta,
    ) -> Dict[str, Any] | None:
        camera_id = item.get("camera_id")
        timestamp_str = item.get("timestamp")
        if not camera_id or not timestamp_str:
            return None
        try:
            event_time = datetime.fromisoformat(timestamp_str)
        except Exception:  # pylint: disable=broad-except
            return None
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        if now - event_time > max_age:
            return None
        detections = item.get("detections") or []
        return {
            "camera_id": camera_id,
            "timestamp": event_time,
            "detections": detections,
        }
