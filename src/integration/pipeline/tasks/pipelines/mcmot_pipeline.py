"""Working hours pipeline composed of multiple stages."""
from __future__ import annotations

import time
from typing import List

from smart_workflow import BaseTask, TaskContext, TaskResult

from integration.pipeline.tasks.base import QuietTaskBase
from integration.pipeline.tasks.summary import (
    SUMMARY_INTERVAL_SECONDS,
    render_pipeline_summary,
    reset_pipeline_summary,
)
from integration.pipeline.tasks.nodes.ingestion.task import IngestionTask
from integration.pipeline.tasks.nodes.tracking.task import MCMOTTask
from integration.pipeline.tasks.nodes.rules.task import RuleEvaluationTask
from integration.pipeline.tasks.nodes.event_dispatch.task import EventDispatchTask


class MCMOTPipelineTask(QuietTaskBase):
    name = "mcmot_pipeline"

    def __init__(self, context: TaskContext, nodes: List[BaseTask] | None = None) -> None:
        self.pipeline_nodes: List[BaseTask] = nodes if nodes is not None else self._build_nodes(context)
        self._last_summary_time = 0.0
        configured_interval = getattr(context.config, "pipeline_summary_interval_seconds", SUMMARY_INTERVAL_SECONDS)
        try:
            self._summary_interval_seconds = float(configured_interval)
        except (TypeError, ValueError):
            self._summary_interval_seconds = SUMMARY_INTERVAL_SECONDS
        if self._summary_interval_seconds <= 0:
            self._summary_interval_seconds = SUMMARY_INTERVAL_SECONDS

    def run(self, context: TaskContext) -> TaskResult:
        reset_pipeline_summary(context)
        try:
            for node in self.pipeline_nodes:
                node.execute(context)
        except Exception:
            self._maybe_log_summary(context, status="error")
            raise
        self._maybe_log_summary(context, status="ok")
        context.logger.debug("mcmot pipeline completed")
        return TaskResult(status="mcmot_pipeline_done")

    def _build_nodes(self, context: TaskContext) -> List[BaseTask]:
        nodes: List[BaseTask] = [
            IngestionTask(context),
            MCMOTTask(context),
        ]
        format_task = self._build_format_task(context)
        if format_task:
            nodes.append(format_task)
        nodes.append(RuleEvaluationTask(context))
        nodes.append(EventDispatchTask(context))
        return nodes

    def _build_format_task(self, context: TaskContext) -> BaseTask | None:
        cfg = getattr(context.config, "format_task", None)
        enabled = getattr(cfg, "enabled", True)
        if not enabled:
            context.logger.info("FORMAT_TASK_ENABLED=0，略過格式轉換節點")
            return None
        from integration.pipeline.tasks.nodes.formatting.task import (
            FormatConversionTask,
        )

        strategy = getattr(cfg, "strategy_class", None)
        if strategy:
            context.logger.info("使用格式轉換策略：%s", strategy)
        else:
            context.logger.info("使用預設格式轉換策略")
        return FormatConversionTask(context)

    @classmethod
    def describe_flow(cls, config) -> str:
        def _class_name(path: str | None, default: str) -> str:
            if not path:
                return default
            if ":" in path:
                return path.split(":", 1)[1]
            return path.rsplit(".", 1)[-1]

        ingestion_handler = _class_name(
            getattr(getattr(config, "ingestion_task", None), "engine_class", None),
            "DefaultIngestionEngine",
        )
        tracking_handler = _class_name(
            getattr(getattr(config, "tracking_task", None), "engine_class", None),
            "DefaultTrackingHandler",
        )
        format_engine = _class_name(
            getattr(getattr(config, "format_task", None), "strategy_class", None),
            "DefaultFormatEngine",
        )
        rules_engine = _class_name(
            getattr(getattr(config, "rules", None), "engine_class", None),
            "DefaultRuleEngine",
        )
        dispatch_engine = _class_name(
            getattr(getattr(config, "event_dispatch", None), "engine_class", None),
            "DefaultEventDispatchEngine",
        )

        return (
            f"IngestionTask(engine={ingestion_handler}) -> "
            f"MCMOTTask(handler={tracking_handler}, engine=MCMOTEngine) -> "
            f"FormatConversionTask(strategy={format_engine}) -> "
            f"RuleEvaluationTask(engine={rules_engine}) -> "
            f"EventDispatchTask(engine={dispatch_engine})"
        )

    def _maybe_log_summary(self, context: TaskContext, status: str) -> None:
        now = time.monotonic()
        if self._last_summary_time > 0.0:
            elapsed = now - self._last_summary_time
            if elapsed < self._summary_interval_seconds:
                return

        phase_state = context.get_resource("phase_task_state")
        phase_name = "-"
        if isinstance(phase_state, dict):
            phase_name = str(phase_state.get("last_phase") or "-")

        summary = render_pipeline_summary(
            context,
            phase_name,
            self._summary_interval_seconds,
            status=status,
        )
        context.logger.info(summary)
        self._last_summary_time = now
