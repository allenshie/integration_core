"""Engine objects for formatting MC-MOT output."""
from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from importlib import import_module
from typing import Any, Dict, Iterable, Type

from smart_workflow import TaskContext, TaskError

from .expect_output import ExpectOutputTransformer


class BaseFormatEngine(ABC):
    """Interface for converting MC-MOT result into downstream payload."""

    @abstractmethod
    def build_payload(
        self,
        context: TaskContext,
        events: Iterable[Dict[str, Any]],
        tracked: Iterable[Dict[str, Any]],
        global_objects: Iterable[Dict[str, Any]],
        snapshot_path: str | None,
    ) -> Dict[str, Any]:
        """Return a dict to store in `rules_payload`."""


class LegacyFormatEngine(BaseFormatEngine):
    """Original summary logic used by the integration core."""

    def __init__(self, timezone_override: timezone | None = None) -> None:
        self._timezone = timezone_override or timezone.utc
        self._expect_transformer = ExpectOutputTransformer(tz=self._timezone)

    def build_payload(
        self,
        context: TaskContext,
        events: Iterable[Dict[str, Any]],
        tracked: Iterable[Dict[str, Any]],
        global_objects: Iterable[Dict[str, Any]],
        snapshot_path: str | None,
    ) -> Dict[str, Any]:
        events_list = list(events)
        tracked_list = list(tracked)
        global_list = list(global_objects)
        expect_output = self._expect_transformer.transform(tracked_list, global_list)
        payload = {
            "events": events_list,
            "tracked_objects": tracked_list,
            "global_objects": global_list,
            "camera_summary": self._summarize_by_camera(tracked_list),
            "global_summary": self._summarize_global(global_list),
            "metadata": {
                "generated_at": datetime.now(self._timezone).isoformat(),
                "global_map_snapshot": snapshot_path,
            },
            "expect_output": expect_output,
        }
        return payload

    @staticmethod
    def _summarize_by_camera(tracked: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        summary: Dict[str, Dict[str, Any]] = {}
        for item in tracked:
            camera_id = item.get("camera_id") or "unknown"
            camera_entry = summary.setdefault(camera_id, {"total": 0, "classes": {}})
            camera_entry["total"] += 1
            class_name = item.get("class_name") or "unknown"
            classes = camera_entry.setdefault("classes", {})
            classes[class_name] = classes.get(class_name, 0) + 1
        return summary

    @staticmethod
    def _summarize_global(global_objects: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        total = 0
        class_counter: Dict[str, int] = {}
        for obj in global_objects:
            total += 1
            class_name = obj.get("class_name") or "unknown"
            class_counter[class_name] = class_counter.get(class_name, 0) + 1
        return {"total": total, "classes": class_counter}


class DefaultFormatEngine(BaseFormatEngine):
    """Format payload to input_schema-v5 for SmartWarehouseEngine."""

    def __init__(self, timezone_override: timezone | None = None) -> None:
        self._timezone = timezone_override or timezone.utc

    def build_payload(
        self,
        context: TaskContext,
        events: Iterable[Dict[str, Any]],
        tracked: Iterable[Dict[str, Any]],
        global_objects: Iterable[Dict[str, Any]],
        snapshot_path: str | None,
    ) -> Dict[str, Any]:
        events_list = list(events)
        tracked_list = list(tracked)
        global_list = list(global_objects)
        return {
            "overall_metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            "mcmot_data": self._build_mcmot_data(global_list),
            "camera_data": self._build_camera_data(events_list),
            "object_id_mapping": self._build_object_id_mapping(tracked_list),
        }

    @staticmethod
    def _build_mcmot_data(objects: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        for item in objects:
            global_id = item.get("global_id")
            if global_id is None:
                continue
            class_name = item.get("class_name") or "unknown"
            result[f"{class_name}_{global_id}"] = {
                "class_name": item.get("class_name") or "unknown",
                "coordinate_location": DefaultFormatEngine._extract_coordinates(item),
                "state": item.get("state") or "normal",
            }
        return result

    @staticmethod
    def _build_camera_data(events: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        from .models import DetectionObject

        cameras: Dict[str, Dict[str, Any]] = {}
        for event in events:
            camera_id = event.get("camera_id")
            if not camera_id:
                continue
            detections = event.get("detections") or []
            camera_entry = cameras.setdefault(camera_id, {"object_metadata": {}})
            for idx, det in enumerate(detections):
                class_name = det.get("class_name") or det.get("label") or "unknown"
                local_id = det.get("track_id", det.get("local_id"))
                if local_id is None:
                    local_id = idx
                obj_id = f"{class_name}_{local_id}"
                obj = DetectionObject.from_detection(det)
                camera_entry["object_metadata"][obj_id] = obj.to_dict()
        return cameras

    @staticmethod
    def _build_object_id_mapping(tracked: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
        mapping: Dict[str, Dict[str, str]] = {}
        for item in tracked:
            global_id = item.get("global_id")
            camera_id = item.get("camera_id")
            local_id = item.get("local_id")
            class_name = item.get("class_name") or "unknown"
            if global_id is None or not camera_id or local_id is None:
                continue
            entry = mapping.setdefault(f"{class_name}_{global_id}", {})
            entry[camera_id] = f"{class_name}_{local_id}"
        return mapping

    @staticmethod
    def _extract_coordinates(obj: Dict[str, Any]) -> list[float]:
        trajectory = obj.get("trajectory") or []
        if trajectory:
            last = trajectory[-1]
            if isinstance(last, dict):
                x = last.get("x")
                y = last.get("y")
            elif isinstance(last, (list, tuple)) and len(last) >= 3:
                _, x, y = last[0:3]
            else:
                x = y = None
            if x is not None and y is not None:
                try:
                    return [float(x), float(y)]
                except (TypeError, ValueError):
                    pass
        position = obj.get("global_position")
        if isinstance(position, dict):
            x = position.get("x")
            y = position.get("y")
            if x is not None and y is not None:
                try:
                    return [float(x), float(y)]
                except (TypeError, ValueError):
                    pass
        return [0.0, 0.0]


def load_format_engine(path: str) -> Type[BaseFormatEngine]:
    if ":" in path:
        module_name, class_name = path.split(":", 1)
    elif "." in path:
        module_name, class_name = path.rsplit(".", 1)
    else:
        raise TaskError(f"無法解析格式策略路徑：{path}")

    module = import_module(module_name)
    attr = getattr(module, class_name, None)
    if attr is None or not inspect.isclass(attr):
        raise TaskError(f"在模組 {module_name} 找不到格式策略 {class_name}")
    if not issubclass(attr, BaseFormatEngine):
        raise TaskError(f"{class_name} 必須繼承 BaseFormatEngine")
    return attr
