"""Ingestion stage task."""
from __future__ import annotations

from smart_workflow import TaskContext, TaskResult, TaskError

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
        context.set_resource("edge_events_latest", result.events)
        store_stage_stats(
            context,
            INGESTION_STATS_RESOURCE,
            {
                "raw": result.raw_count,
                "events": len(result.events),
                "dropped": result.dropped,
            },
        )
        context.logger.debug(
            "匯入 %d 台相機的最新事件（原始 %d 筆，丟棄 %d 筆）",
            len(result.events),
            result.raw_count,
            result.dropped,
        )
        return TaskResult(
            status="ingestion_done",
            payload={
                "events": len(result.events),
                "raw": result.raw_count,
                "dropped": result.dropped,
            },
        )

    def _init_engine(self, context: TaskContext | None) -> BaseIngestionEngine:
        cfg = getattr(context.config, "ingestion_task", None) if context else None
        engine_path = getattr(cfg, "engine_class", None) if cfg else None
        if not engine_path:
            return DefaultIngestionEngine(context=context)
        try:
            engine_cls = load_ingestion_engine(engine_path)
        except Exception as exc:  # pylint: disable=broad-except
            raise TaskError(f"無法載入 Ingestion Engine：{engine_path}") from exc
        try:
            return engine_cls(context=context)
        except TypeError:
            try:
                return engine_cls()
            except TypeError as exc:  # pragma: no cover
                raise TaskError(f"Ingestion Engine {engine_path} 無法初始化") from exc
