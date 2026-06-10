"""Ingestion stage task."""
from __future__ import annotations

from smart_workflow import TaskContext, TaskResult

from integration.pipeline.tasks.base import QuietTaskBase
from integration.pipeline.tasks.summary import INGESTION_STATS_RESOURCE, store_stage_stats

from .engine import BaseIngestionEngine, DefaultIngestionEngine, load_ingestion_engine


class IngestionTask(QuietTaskBase):
    name = "ingestion"

    def __init__(self, context: TaskContext | None = None) -> None:
        self._engine: BaseIngestionEngine | None = None

    def run(self, context: TaskContext) -> TaskResult:
        if self._engine is None:
            self._engine = self._init_engine(context)
        store = context.require_resource("edge_event_store")
        raw_events = store.pop_all()
        result = self._engine.process(context, raw_events)
        context.set_resource("edge_events", result.events)
        context.set_resource("pipeline_has_new_data", result.has_new_data)
        context.set_resource("pipeline_dirty_camera_ids", list(result.dirty_camera_ids))
        if result.has_new_data:
            context.set_resource("edge_events_latest", result.events)
        store_stage_stats(
            context,
            INGESTION_STATS_RESOURCE,
            {
                "raw": result.raw_count,
                "events": len(result.events),
                "dropped": result.dropped,
                "duplicates": result.duplicate_count,
            },
        )
        context.logger.debug(
            "匯入 %d 台相機的最新事件（原始 %d 筆，丟棄 %d 筆，重複 %d 筆，new=%s）",
            len(result.events),
            result.raw_count,
            result.dropped,
            result.duplicate_count,
            result.has_new_data,
        )
        return TaskResult(
            status="ingestion_done",
            payload={
                "events": len(result.events),
                "raw": result.raw_count,
                "dropped": result.dropped,
                "duplicates": result.duplicate_count,
                "has_new_data": result.has_new_data,
                "dirty_camera_ids": list(result.dirty_camera_ids),
            },
        )

    def _init_engine(self, context: TaskContext | None) -> BaseIngestionEngine:
        cfg = getattr(context.config, "ingestion_task", None) if context else None
        engine_path = getattr(cfg, "engine_class", None) if cfg else None
        return self._init_plugin(
            plugin_name="Ingestion Engine",
            loader=load_ingestion_engine,
            plugin_path=engine_path,
            default_factory=lambda: DefaultIngestionEngine(context=context),
            init_kwargs={"context": context},
        )
