"""Ingestion engine implementations."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Type

from smart_workflow import TaskContext

from integration.pipeline.tasks.plugin_loader import load_plugin_class


@dataclass
class IngestionResult:
    """Normalized ingestion output."""

    events: List[Dict[str, Any]]
    raw_count: int
    dropped: int
    duplicate_count: int = 0
    has_new_data: bool = False
    dirty_camera_ids: List[str] = field(default_factory=list)


class BaseIngestionEngine(ABC):
    """Base interface for ingestion engines."""

    def __init__(self, context: TaskContext | None = None) -> None:
        self._context = context

    @abstractmethod
    def process(self, context: TaskContext, raw_events: List[Dict[str, Any]]) -> IngestionResult:
        """Return deduplicated events and stats."""


class DefaultIngestionEngine(BaseIngestionEngine):
    """Default normalization/dedup logic."""

    def __init__(self, context: TaskContext | None = None) -> None:
        super().__init__(context)
        self._last_seen_by_camera: Dict[str, tuple[str, str, str]] = {}
        if context is None:
            self._max_age_seconds = None
        else:
            edge_cfg = getattr(context.config, "edge_events", None)
            self._max_age_seconds = getattr(edge_cfg, "max_age_seconds", None)
            if self._max_age_seconds is None:
                self._max_age_seconds = getattr(context.config, "edge_event_max_age_seconds", None)

    def process(self, context: TaskContext, raw_events: List[Dict[str, Any]]) -> IngestionResult:
        edge_cfg = getattr(context.config, "edge_events", None)
        configured_max_age = getattr(edge_cfg, "max_age_seconds", None)
        if configured_max_age is None:
            configured_max_age = getattr(context.config, "edge_event_max_age_seconds", 5)
        max_age_seconds = self._max_age_seconds or configured_max_age
        max_age = timedelta(seconds=max_age_seconds)
        now = datetime.now(timezone.utc)

        latest_events: Dict[str, Dict[str, Any]] = {}
        dropped = 0
        duplicate_count = 0
        for item in raw_events:
            parsed = self._normalize_event(item, now, max_age)
            if parsed is None:
                dropped += 1
                continue
            camera_id = parsed["camera_id"]
            current = latest_events.get(camera_id)
            if current is None or self._is_more_recent(parsed, current):
                latest_events[camera_id] = parsed

        deduped_events: List[Dict[str, Any]] = []
        dirty_camera_ids: List[str] = []
        for camera_id, parsed in latest_events.items():
            frame_identity = self._build_event_identity(parsed)
            current_identity = self._last_seen_by_camera.get(camera_id)
            if current_identity == frame_identity:
                duplicate_count += 1
                continue
            self._last_seen_by_camera[camera_id] = frame_identity
            dirty_camera_ids.append(camera_id)
            deduped_events.append(parsed)

        return IngestionResult(
            events=deduped_events,
            raw_count=len(raw_events),
            dropped=dropped,
            duplicate_count=duplicate_count,
            has_new_data=bool(deduped_events),
            dirty_camera_ids=dirty_camera_ids,
        )

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except Exception:  # pylint: disable=broad-except
                return None
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        return None

    @staticmethod
    def _normalize_event(
        item: Dict[str, Any],
        now: datetime,
        max_age: timedelta,
    ) -> Dict[str, Any] | None:
        camera_id = item.get("camera_id")
        timestamp_str = item.get("timestamp")
        if not camera_id or not timestamp_str:
            return None
        event_time = DefaultIngestionEngine._parse_timestamp(timestamp_str)
        if event_time is None:
            return None
        if now - event_time > max_age:
            return None
        capture_ts = DefaultIngestionEngine._parse_timestamp(item.get("capture_ts")) or event_time
        session_id = item.get("session_id")
        if session_id is not None and not isinstance(session_id, str):
            session_id = str(session_id)
        frame_seq = item.get("frame_seq")
        if isinstance(frame_seq, str):
            try:
                frame_seq = int(frame_seq)
            except ValueError:
                frame_seq = None
        elif not isinstance(frame_seq, int) or frame_seq <= 0:
            frame_seq = None
        detections = item.get("detections") or []
        models = item.get("models") or []
        return {
            "camera_id": camera_id,
            "timestamp": event_time,
            "capture_ts": capture_ts,
            "session_id": session_id,
            "frame_seq": frame_seq,
            "detections": detections,
            "models": models,
        }

    @staticmethod
    def _is_more_recent(candidate: Dict[str, Any], current: Dict[str, Any]) -> bool:
        candidate_session = candidate.get("session_id")
        current_session = current.get("session_id")
        candidate_seq = candidate.get("frame_seq")
        current_seq = current.get("frame_seq")
        if (
            isinstance(candidate_session, str)
            and isinstance(current_session, str)
            and candidate_session == current_session
            and isinstance(candidate_seq, int)
            and isinstance(current_seq, int)
        ):
            return candidate_seq > current_seq

        candidate_time = candidate.get("capture_ts") or candidate["timestamp"]
        current_time = current.get("capture_ts") or current["timestamp"]
        if candidate_time != current_time:
            return candidate_time > current_time
        if isinstance(candidate_seq, int) and isinstance(current_seq, int):
            return candidate_seq > current_seq
        return False

    @staticmethod
    def _build_event_identity(event: Dict[str, Any]) -> tuple[str, str, str]:
        session_id = str(event.get("session_id") or "")
        frame_seq = event.get("frame_seq")
        event_time = event.get("capture_ts") or event["timestamp"]
        event_time_key = event_time.isoformat()
        if session_id and isinstance(frame_seq, int):
            return ("frame", session_id, f"{frame_seq}:{event_time_key}")
        return ("legacy", str(event["camera_id"]), event_time_key)


def load_ingestion_engine(path: str) -> Type[BaseIngestionEngine]:
    return load_plugin_class(path, BaseIngestionEngine, "Ingestion Engine")
