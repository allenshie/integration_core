"""Phase controller task switching working/non-working pipelines."""
from __future__ import annotations

from integration.pipeline.control.phase_engine import BasePhaseEngine, TimeBasedPhaseEngine, load_phase_engine
from integration.pipeline.control.scheduler import PipelineScheduler
from smart_workflow import BaseTask, TaskContext, TaskResult, TaskError


class PhaseTask(BaseTask):
    name = "phase_controller"

    def __init__(self, context: TaskContext | None = None) -> None:
        self._engine: BasePhaseEngine | None = self._init_engine(context)

    def run(self, context: TaskContext) -> TaskResult:
        if self._engine is None:
            self._engine = self._init_engine(context)

        if self._engine:
            phase = self._engine.resolve(context)
        else:
            scheduler: PipelineScheduler = context.require_resource("scheduler")
            phase = scheduler.current_phase()
        context.monitor.heartbeat(phase=phase.name)

        pipeline_registry = context.get_resource("pipeline_registry") or {}
        pipeline = pipeline_registry.get(phase.name)
        if pipeline:
            pipeline.execute(context)
            return TaskResult(status="phase_pipeline", payload={"phase": phase.name})
        raise TaskError(f"phase {phase.name} 未設定對應 pipeline")

    def _init_engine(self, context: TaskContext | None) -> BasePhaseEngine:
        cfg = getattr(context.config, "phase_task", None) if context else None
        engine_path = getattr(cfg, "engine_class", None) if cfg else None
        if not engine_path:
            return TimeBasedPhaseEngine(context=context)
        try:
            engine_cls = load_phase_engine(engine_path)
        except Exception as exc:  # pylint: disable=broad-except
            raise TaskError(f"無法載入 Phase Engine：{engine_path}") from exc
        try:
            return engine_cls(context=context)
        except TypeError:
            try:
                return engine_cls()
            except TypeError as exc:  # pragma: no cover
                raise TaskError(f"Phase Engine {engine_path} 無法初始化") from exc
