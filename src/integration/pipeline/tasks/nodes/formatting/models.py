"""Lightweight models for formatting payloads to input_schema-v5."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class DetectionObject:
    """Normalized camera object entry for input_schema-v5."""

    class_name: str
    bbox: List[int] = field(default_factory=list)
    bbox_confidence_score: float = 0.0
    polygon: List[List[int]] = field(default_factory=list)
    polygon_confidence_score: float = 0.0
    keypoint: List[List[int]] = field(default_factory=list)
    keypoint_confidence_score: List[float] = field(default_factory=list)
    state: str = ""

    @classmethod
    def from_detection(cls, det: Dict[str, Any]) -> "DetectionObject":
        class_name = det.get("class_name") or det.get("label") or "unknown"
        bbox = _coerce_int_list(det.get("bbox") or det.get("box") or [])
        bbox_score = float(
            det.get("bbox_confidence_score")
            or det.get("score")
            or det.get("confidence")
            or 0.0
        )
        polygon = _coerce_int_matrix(det.get("polygon") or [])
        polygon_score = float(det.get("polygon_confidence_score") or 0.0)
        keypoint = _coerce_int_matrix(det.get("keypoint") or det.get("keypoints") or [])
        keypoint_score = det.get("keypoint_confidence_score") or []
        if not isinstance(keypoint_score, list):
            keypoint_score = []
        state = det.get("state") or ""
        return cls(
            class_name=class_name,
            bbox=bbox,
            bbox_confidence_score=bbox_score,
            polygon=polygon,
            polygon_confidence_score=polygon_score,
            keypoint=keypoint,
            keypoint_confidence_score=keypoint_score,
            state=state,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_name": self.class_name,
            "bbox": self.bbox,
            "bbox_confidence_score": self.bbox_confidence_score,
            "polygon": self.polygon,
            "polygon_confidence_score": self.polygon_confidence_score,
            "keypoint": self.keypoint,
            "keypoint_confidence_score": self.keypoint_confidence_score,
            "state": self.state,
        }


def _coerce_int_list(value: Any) -> List[int]:
    if not isinstance(value, list):
        return []
    result: List[int] = []
    for item in value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            return []
    return result


def _coerce_int_matrix(value: Any) -> List[List[int]]:
    if not isinstance(value, list):
        return []
    result: List[List[int]] = []
    for row in value:
        if not isinstance(row, list):
            return []
        coerced = _coerce_int_list(row)
        if not coerced:
            return []
        result.append(coerced)
    return result
