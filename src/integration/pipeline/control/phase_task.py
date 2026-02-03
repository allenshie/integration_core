"""Phase controller task switching working/non-working pipelines."""
from __future__ import annotations

import time

from smart_messaging_core import MessagingClient, MessagingConfig, MqttConfig

from integration.pipeline.control.phase_engine import BasePhaseEngine, TimeBasedPhaseEngine, load_phase_engine
from integration.pipeline.control.scheduler import PipelineScheduler
from smart_workflow import BaseTask, TaskContext, TaskResult, TaskError


class PhaseTask(BaseTask):
    name = "phase_controller"

    def __init__(self, context: TaskContext | None = None) -> None:
        self._engine: BasePhaseEngine | None = self._init_engine(context)
        self._messaging: MessagingClient | None = None
        self._last_phase: str | None = None
        self._last_publish_time: float = 0.0
        self._last_run_time_by_phase: dict[str, float] = {}

    def run(self, context: TaskContext) -> TaskResult:
        # 1) 初始化 phase engine（僅第一次）
        if self._engine is None:
            self._engine = self._init_engine(context)

        # 2) 解析目前工作階段（phase）
        if self._engine:
            phase = self._engine.resolve(context)
        else:
            scheduler: PipelineScheduler = context.require_resource("scheduler")
            phase = scheduler.current_phase()

        # 3) 回報 heartbeat、必要時推播 phase 變更
        context.monitor.heartbeat(phase=phase.name)
        self._maybe_publish_phase(context, phase.name)

        # 4) 根據 phase 的 interval_seconds 進行節流判斷
        phase_policies = context.get_resource("pipeline_policies") or {}
        policy = phase_policies.get(phase.name)
        if policy is not None and policy.enabled:
            now = time.time()
            last_run = self._last_run_time_by_phase.get(phase.name, 0.0)
            if (now - last_run) < policy.interval:
                return TaskResult(status="phase_skipped", payload={"phase": phase.name})

        # 5) 依 phase 取得對應 pipeline 並執行
        pipeline_registry = context.get_resource("pipeline_registry") or {}
        pipeline = pipeline_registry.get(phase.name)
        if pipeline:
            pipeline.execute(context)
            self._last_run_time_by_phase[phase.name] = time.time()
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

    def _maybe_publish_phase(self, context: TaskContext, phase_name: str) -> None:
        cfg = getattr(context.config, "mqtt", None)
        if not cfg or not cfg.enabled:
            return
        now = time.time()
        should_publish = phase_name != self._last_phase
        if not should_publish and cfg.heartbeat_seconds > 0:
            should_publish = (now - self._last_publish_time) >= cfg.heartbeat_seconds
        if not should_publish:
            return

        if self._messaging is None:
            messaging_cfg = MessagingConfig(
                publish_backend="mqtt",
                subscribe_backend="none",
                mqtt=MqttConfig(
                    host=cfg.host,
                    port=cfg.port,
                    qos=cfg.qos,
                    retain=cfg.retain,
                    client_id=cfg.client_id,
                ),
            )
            self._messaging = MessagingClient(messaging_cfg)

        payload = {"phase": phase_name, "timestamp": time.time()}
        if self._messaging.publish(cfg.topic, payload):
            self._last_phase = phase_name
            self._last_publish_time = now
