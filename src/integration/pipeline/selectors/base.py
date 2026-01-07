"""Base selector interface for choosing which pipeline to execute."""
from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from importlib import import_module
from typing import Any, Dict, Type

from smart_workflow import TaskContext, TaskError


@dataclass(slots=True)
class PipelineSelection:
    """Represents the selector decision."""

    name: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class BasePipelineSelector(ABC):
    """Strategy interface used by PhaseTask to選擇 pipeline."""

    def __init__(self, context: TaskContext | None = None) -> None:
        self._context = context

    @abstractmethod
    def select(self, context: TaskContext) -> PipelineSelection:
        """Return the pipeline that should run for this iteration."""


def load_selector_class(path: str) -> Type[BasePipelineSelector]:
    if ":" in path:
        module_name, class_name = path.split(":", 1)
    elif "." in path:
        module_name, class_name = path.rsplit(".", 1)
    else:
        raise TaskError(f"無法解析 Pipeline Selector 路徑：{path}")

    module = import_module(module_name)
    attr = getattr(module, class_name, None)
    if attr is None or not inspect.isclass(attr):
        raise TaskError(f"在模組 {module_name} 找不到 Selector 類別 {class_name}")
    if not issubclass(attr, BasePipelineSelector):
        raise TaskError(f"{class_name} 必須繼承 BasePipelineSelector")
    return attr
