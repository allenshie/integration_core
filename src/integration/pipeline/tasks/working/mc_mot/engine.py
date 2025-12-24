"""Wrapper around the vendored MC-MOT coordinator."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from integration.mcmot.config.schema import BaseConfig as MCMOTConfig
from integration.mcmot.services.mcmot_coordinator import MCMOTCoordinator


@dataclass
class MCMOTResult:
    tracked_objects: List[Dict[str, Any]]
    global_objects: List[Dict[str, Any]]


class MCMOTEngine:
    """Adapter that feeds integration events into the MC-MOT coordinator."""

    def __init__(self, config: MCMOTConfig, logger: logging.Logger | None = None) -> None:
        self._log = logger or logging.getLogger("mcmot.engine")
        self._config = config
        self._coordinator = MCMOTCoordinator(config=config)
        self._log.info("MC-MOT coordinator ready with %d cameras", len(config.cameras))

    def process_events(self, events: Iterable[Dict[str, Any]]) -> MCMOTResult:
        tracked_payload: List[Dict[str, Any]] = []
        for event in events:
            camera_id = event.get("camera_id")
            timestamp = self._ensure_timestamp(event.get("timestamp"))
            detections = self._build_detections(event.get("detections") or [])
            if not camera_id or not detections:
                continue
            tracked = self._coordinator.process_detected_objects(
                detected_objects=detections,
                camera_id=camera_id,
                timestamp=timestamp,
            )
            if tracked:
                tracked_payload.extend(self._serialize_tracked(camera_id, tracked))

        self._coordinator.finalize_global_updates()
        global_objects = [self._serialize_global(obj) for obj in self._coordinator.get_all_global_objects()]
        return MCMOTResult(tracked_objects=tracked_payload, global_objects=global_objects)

    def _build_detections(self, detections: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted: List[Dict[str, Any]] = []
        for det in detections:
            bbox = det.get("bbox") or det.get("box")
            if not bbox or len(bbox) != 4:
                continue
            local_id = det.get("local_id", det.get("track_id"))
            if local_id is None:
                continue
            class_name = det.get("class_name") or det.get("label")
            if class_name is None:
                continue
            score = det.get("score") or det.get("confidence") or 0.0
            formatted.append(
                {
                    "class_name": class_name,
                    "local_id": int(local_id),
                    "global_id": det.get("global_id"),
                    "bbox": [int(x) for x in bbox],
                    "score": float(score),
                    "feature": det.get("feature"),
                }
            )
        return formatted

    def _serialize_tracked(self, camera_id: str, tracked: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        payload: List[Dict[str, Any]] = []
        for item in tracked:
            global_position = self._extract_latest_xy(item.get("global_trajectory"))
            payload.append(
                {
                    "camera_id": camera_id,
                    "class_name": item.get("class_name"),
                    "local_id": item.get("local_id"),
                    "global_id": item.get("global_id"),
                    "bbox": item.get("bbox"),
                    "score": item.get("score"),
                    "timestamp": self._to_iso(item.get("timestamp")),
                    "global_position": global_position,
                }
            )
        return payload

    def _serialize_global(self, obj: Any) -> Dict[str, Any]:
        trajectory = []
        for entry in getattr(obj, "trajectory", []) or []:
            ts, x, y = entry
            trajectory.append(
                {
                    "timestamp": self._to_iso(ts),
                    "x": float(x),
                    "y": float(y),
                }
            )
        update_time = getattr(obj, "update_time", None)
        return {
            "global_id": getattr(obj, "global_id", None),
            "class_name": getattr(obj, "class_name", None),
            "camera_id": getattr(obj, "camera_id", None),
            "trajectory": trajectory,
            "updated_at": self._to_iso(update_time),
        }

    @staticmethod
    def _ensure_timestamp(value: Any) -> datetime:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        raise ValueError("事件缺少 timestamp")

    @staticmethod
    def _to_iso(value: Any) -> str | None:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.isoformat() + "Z"
            return value.isoformat()
        return None

    @staticmethod
    def _extract_latest_xy(trajectory: Any) -> Dict[str, float] | None:
        if not trajectory:
            return None
        try:
            last = trajectory[-1]
        except (TypeError, IndexError):
            return None
        x: float | None
        y: float | None
        if isinstance(last, Mapping):
            x = last.get("x")
            y = last.get("y")
        elif isinstance(last, Sequence) and len(last) >= 3:
            x = last[1]
            y = last[2]
        else:
            return None
        if x is None or y is None:
            return None
        try:
            return {"x": float(x), "y": float(y)}
        except (TypeError, ValueError):
            return None
