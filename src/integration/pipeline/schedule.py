"""Pipeline schedule loader for phase-based pipelines."""
from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Tuple, Type

from smart_workflow import BaseTask, TaskError

from integration.utils.paths import get_core_root


@dataclass(frozen=True)
class PipelineSpec:
    name: str
    class_path: str
    kwargs: Dict[str, Any]
    enabled_env: str | None = None


def resolve_schedule_path(raw_path: str | Path) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = (get_core_root() / path).resolve()
    return path


def load_pipeline_schedule(path: str | Path) -> Tuple[Dict[str, PipelineSpec], Dict[str, str]]:
    schedule_path = resolve_schedule_path(path)
    if not schedule_path.exists():
        raise TaskError(f"找不到 pipeline schedule：{schedule_path}")
    try:
        data = json.loads(schedule_path.read_text())
    except json.JSONDecodeError as exc:
        raise TaskError(f"pipeline schedule 格式錯誤：{exc}") from exc

    if not isinstance(data, dict):
        raise TaskError("pipeline schedule 必須是 JSON 物件")

    pipelines: Dict[str, PipelineSpec] = {}
    phases: Dict[str, str] = {}

    raw_pipelines = data.get("pipelines")
    raw_phases = data.get("phases")
    if raw_pipelines is None or raw_phases is None:
        raise TaskError("pipeline schedule 需包含 pipelines 與 phases")
    if not isinstance(raw_pipelines, dict):
        raise TaskError("pipeline schedule pipelines 必須是物件")
    if not isinstance(raw_phases, dict):
        raise TaskError("pipeline schedule phases 必須是物件")

    for name, cfg in raw_pipelines.items():
        spec = _build_pipeline_spec(name, cfg)
        pipelines[spec.name] = spec

    for phase_name, pipeline_name in raw_phases.items():
        if not isinstance(pipeline_name, str):
            raise TaskError(f"phase {phase_name} 必須指向 pipeline 名稱")
        phases[phase_name] = pipeline_name

    return pipelines, phases


def load_task_class(path: str) -> Type[BaseTask]:
    if ":" in path:
        module_name, class_name = path.split(":", 1)
    elif "." in path:
        module_name, class_name = path.rsplit(".", 1)
    else:
        raise TaskError(f"無法解析 Task 路徑：{path}")
    module = import_module(module_name)
    attr = getattr(module, class_name, None)
    if attr is None or not inspect.isclass(attr):
        raise TaskError(f"在模組 {module_name} 找不到 Task {class_name}")
    if not issubclass(attr, BaseTask):
        raise TaskError(f"{class_name} 必須繼承 BaseTask")
    return attr


def _build_pipeline_spec(name: str, cfg: Dict[str, Any]) -> PipelineSpec:
    if not isinstance(cfg, dict):
        raise TaskError(f"pipeline {name} 設定必須是物件")
    class_path = cfg.get("class") or cfg.get("pipeline_class")
    if not class_path:
        raise TaskError(f"pipeline {name} 缺少 class/pipeline_class")
    kwargs = cfg.get("kwargs") or cfg.get("params") or {}
    if kwargs is None:
        kwargs = {}
    if not isinstance(kwargs, dict):
        raise TaskError(f"pipeline {name} kwargs 必須是物件")
    enabled_env = cfg.get("enabled_env")
    return PipelineSpec(name=name, class_path=str(class_path), kwargs=kwargs, enabled_env=enabled_env)
