"""Normalize MC-MOT output for downstream rules."""
from __future__ import annotations

from smart_workflow import TaskContext, TaskError, TaskResult

from integration.pipeline.tasks.base import QuietTaskBase
from integration.pipeline.tasks.summary import FORMAT_STATS_RESOURCE, store_stage_stats
from .engine import BaseFormatEngine, DefaultFormatEngine, load_format_engine


class FormatConversionTask(QuietTaskBase):
    """Convert MC-MOT result into a shared payload for rule tasks."""

    name = "format_conversion"

    def __init__(self, context: TaskContext | None = None) -> None:
        self._strategy: BaseFormatEngine | None = None

    def run(self, context: TaskContext) -> TaskResult:
        if self._strategy is None:
            self._strategy = self._init_strategy(context)
        events = context.get_resource("edge_events") or []
        tracked = context.get_resource("mc_mot_tracked") or []
        global_objects = context.get_resource("mc_mot_global_objects") or []
        snapshot = context.get_resource("global_map_snapshot")

        payload = self._strategy.build_payload(context, events, tracked, global_objects, snapshot)
        context.set_resource("rules_payload", payload)
        store_stage_stats(
            context,
            FORMAT_STATS_RESOURCE,
            {
                "events": len(events),
                "tracked": len(tracked),
                "global": len(global_objects),
                "signal_groups": len((payload.get("overall_metadata") or {}).get("signal_groups") or []),
            },
        )
        context.logger.debug(
            "格式轉換完成：事件 %d、追蹤 %d、全域物件 %d",
            len(events),
            len(tracked),
            len(global_objects),
        )
        return TaskResult(
            status="format_conversion_done",
            payload={
                "events": len(events),
                "tracked": len(tracked),
                "global_objects": len(global_objects),
            },
        )

    def _init_strategy(self, context: TaskContext | None) -> BaseFormatEngine:
        tz = getattr(context.config, "timezone", None) if context else None
        cfg = getattr(context.config, "format_task", None) if context else None
        engine_path = getattr(cfg, "strategy_class", None)
        if not engine_path:
            return DefaultFormatEngine(timezone_override=tz)

        try:
            strategy_cls = load_format_engine(engine_path)
        except Exception as exc:  # pylint: disable=broad-except
            raise TaskError(f"無法載入格式引擎：{engine_path}") from exc

        try:
            return strategy_cls(context=context)
        except TypeError:
            try:
                return strategy_cls()
            except TypeError as exc:  # pragma: no cover - fall back error
                raise TaskError(f"格式引擎 {engine_path} 無法初始化") from exc
