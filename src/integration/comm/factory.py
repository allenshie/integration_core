"""Factory for building edge communication adapters."""
from __future__ import annotations

from smart_workflow import TaskError

from .base import EdgeCommAdapter
from .http_adapter import HttpEdgeCommAdapter
from .mqtt_adapter import MqttEdgeCommAdapter


def build_edge_comm_adapter(config, logger=None) -> EdgeCommAdapter:
    backend = (getattr(config, "edge_event_backend", "") or "").strip().lower()
    if backend == "mqtt":
        return MqttEdgeCommAdapter(config, logger=logger)
    if backend == "http":
        return HttpEdgeCommAdapter(config, logger=logger)
    raise TaskError(f"不支援的 EDGE_EVENT_BACKEND: {backend}")
