"""Integration pipeline composition and startup tasks."""
from __future__ import annotations

import os

from smart_workflow import BaseTask, TaskContext, TaskResult, TaskError

from integration.pipeline.schedule import load_pipeline_schedule, load_task_class


class InitPipelineTask(BaseTask):
    """Bootstrap working pipeline(s) and store them in TaskContext."""

    name = "integration-pipeline-init"

    def run(self, context: TaskContext) -> TaskResult:
        pipeline_registry = self._build_pipeline_registry(context)
        context.set_resource("pipeline_registry", pipeline_registry)
        if os.getenv("CONFIG_SUMMARY", "").strip().lower() in {"1", "true", "yes"}:
            context.logger.info(self._format_pipeline_summary(pipeline_registry, context))
        return TaskResult(status="pipeline_initialised", payload={"pipelines": list(pipeline_registry.keys())})

    def _build_pipeline_registry(self, context: TaskContext) -> dict[str, BaseTask] | None:
        schedule_path = getattr(context.config, "pipeline_schedule_path", None)
        if not schedule_path:
            raise TaskError("PIPELINE_SCHEDULE_PATH 未設定")
        pipelines, phases, phase_policies = load_pipeline_schedule(schedule_path)
        pipeline_instances: dict[str, BaseTask] = {}
        for name, spec in pipelines.items():
            if spec.enabled_env and os.getenv(spec.enabled_env, "").strip().lower() in {"0", "false", "no", "off"}:
                continue
            pipeline_cls = load_task_class(spec.class_path)
            kwargs = dict(spec.kwargs)
            if "context" not in kwargs:
                try:
                    pipeline = pipeline_cls(context=context, **kwargs)
                except TypeError:
                    pipeline = pipeline_cls(**kwargs)
            else:
                pipeline = pipeline_cls(**kwargs)
            pipeline_instances[name] = pipeline

        registry: dict[str, BaseTask] = {}
        for phase_name, pipeline_name in phases.items():
            pipeline = pipeline_instances.get(pipeline_name)
            if not pipeline:
                raise TaskError(f"phase {phase_name} 找不到 pipeline: {pipeline_name}")
            registry[phase_name] = pipeline
        context.set_resource("pipeline_policies", phase_policies)
        return registry

    def _format_pipeline_summary(self, registry: dict[str, BaseTask], context: TaskContext) -> str:
        lines = ["pipeline registry summary:"]
        for phase, pipeline in registry.items():
            pipeline_name = pipeline.__class__.__name__
            nodes = self._describe_nodes(pipeline, context)
            lines.append(f"- phase={phase} pipeline={pipeline_name}")
            if nodes:
                lines.append(f"  flow: {nodes}")
        return "\n".join(lines)

    def _describe_nodes(self, pipeline: BaseTask, context: TaskContext) -> str:
        nodes = []
        pipeline_nodes = getattr(pipeline, "pipeline_nodes", None)
        if pipeline_nodes is None:
            pipeline_nodes = getattr(pipeline, "_nodes", None)
        if not pipeline_nodes:
            return ""
        for node in pipeline_nodes:
            nodes.append(self._describe_node(node, context))
        return " -> ".join(nodes)

    def _describe_node(self, node: BaseTask, context: TaskContext) -> str:
        parts = [node.__class__.__name__]
        handler = getattr(node, "_handler", None)
        if handler is not None:
            parts.append(f"handler={handler.__class__.__name__}")
        strategy = getattr(node, "_strategy", None)
        if strategy is not None:
            parts.append(f"strategy={strategy.__class__.__name__}")
        engine = getattr(node, "_engine", None)
        if engine is not None:
            parts.append(f"engine={engine.__class__.__name__}")
        if node.__class__.__name__ == "MCMOTTask":
            mcmot_engine = context.get_resource("mcmot_engine")
            if mcmot_engine is not None:
                parts.append(f"engine={mcmot_engine.__class__.__name__}")
        return f"{parts[0]}({', '.join(parts[1:])})" if len(parts) > 1 else parts[0]
