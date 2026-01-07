"""Integration pipeline composition and startup tasks."""
from __future__ import annotations

import inspect
from importlib import import_module

from smart_workflow import BaseTask, TaskContext, TaskResult, TaskError

from integration.pipeline.events import get_event_queue
from integration.pipeline.registry import PipelineRegistry
from integration.pipeline.selectors.base import BasePipelineSelector, load_selector_class
from integration.pipeline.selectors.default import WorkingHoursSelector
from integration.pipeline.tasks.working.pipeline import WorkingPipelineTask
from integration.pipeline.tasks.working.mc_mot.engine import MCMOTEngine
from integration.mcmot.visualization.map_overlay import GlobalMapRenderer


class InitPipelineTask(BaseTask):
    """Bootstrap working pipeline(s) and store them in TaskContext."""

    name = "integration-pipeline-init"

    def run(self, context: TaskContext) -> TaskResult:
        self._init_mcmot_resources(context)
        get_event_queue(context)  # ensure queue resource exists

        pipeline_classes = {"working": WorkingPipelineTask}
        pipeline_classes.update(
            {name: self._load_pipeline_attr(path) for name, path in context.config.pipeline.task_classes.items()}
        )

        sleep_map = dict(context.config.pipeline.sleep_seconds)
        registry = PipelineRegistry()
        for name, pipeline_cls in pipeline_classes.items():
            default_sleep = sleep_map.get(name)
            if default_sleep is None and name == "working":
                default_sleep = context.config.loop_interval_seconds
            if default_sleep is None and name == "off_hours" and context.config.non_working_idle_seconds:
                # 保留向後相容：若子專案未設定 sleep，可沿用 NON_WORKING_IDLE_SECONDS
                default_sleep = context.config.non_working_idle_seconds
            registry.register(name, self._instantiate_pipeline(pipeline_cls, context), default_sleep=default_sleep)

        context.set_resource("pipeline_registry", registry)
        selector = self._build_selector(context)
        context.set_resource("pipeline_selector", selector)
        context.logger.info("已載入 pipelines：%s", ", ".join(registry.names()))
        return TaskResult(status="pipeline_initialised")

    def _load_pipeline_attr(self, class_path: str):
        attr = self._import_attr(class_path)
        if inspect.isclass(attr) and issubclass(attr, BaseTask):
            return attr
        if callable(attr):
            return attr
        raise TaskError(f"Pipeline {class_path} 必須是 BaseTask 子類或可呼叫工廠")

    def _build_selector(self, context: TaskContext) -> BasePipelineSelector:
        selector_path = context.config.pipeline.selector_class
        if selector_path:
            selector_cls = load_selector_class(selector_path)
            return selector_cls(context)
        return WorkingHoursSelector(context)

    def _import_attr(self, path: str):
        if ":" in path:
            module_name, attr_name = path.split(":", 1)
        elif "." in path:
            module_name, attr_name = path.rsplit(".", 1)
        else:
            raise TaskError(f"無法解析 Pipeline 類別路徑：{path}")

        module = import_module(module_name)
        attr = getattr(module, attr_name, None)
        if attr is None:
            raise TaskError(f"在模組 {module_name} 找不到 {attr_name}")
        return attr

    def _instantiate_pipeline(self, pipeline_cls, context: TaskContext) -> BaseTask:
        if inspect.isclass(pipeline_cls) and issubclass(pipeline_cls, BaseTask):
            try:
                return pipeline_cls(context)
            except TypeError:
                return pipeline_cls()
        if callable(pipeline_cls):
            return pipeline_cls(context)
        raise TaskError("Pipeline 類別/工廠無法被實例化")

    def _init_mcmot_resources(self, context: TaskContext) -> None:
        if not context.config.mcmot_enabled:
            context.logger.info("MC-MOT disabled via configuration")
            return

        if context.config.mcmot is None:
            raise TaskError("MC-MOT 已啟用但設定未載入")

        engine = MCMOTEngine(config=context.config.mcmot, logger=context.logger)
        context.set_resource("mcmot_engine", engine)
        context.logger.info("MC-MOT engine initialized")

        vis_cfg = getattr(context.config, "global_map_visualization", None)
        if not (vis_cfg and vis_cfg.enabled):
            return

        map_cfg = context.config.mcmot.map
        if map_cfg is None:
            context.logger.warning("啟用了全局可視化但 mcmot map 未設定")
            return

        renderer = GlobalMapRenderer(
            map_cfg=map_cfg,
            vis_cfg=vis_cfg,
            logger=context.logger,
            camera_configs=context.config.mcmot.cameras,
        )
        context.set_resource("global_map_renderer", renderer)
        context.logger.info("Global map renderer initialized")
