"""Shared helpers for loading task plugin classes."""
from __future__ import annotations

import inspect
from importlib import import_module
from typing import Type, TypeVar

from smart_workflow import TaskError

T = TypeVar("T")


def load_plugin_class(path: str, base_class: Type[T], plugin_name: str) -> Type[T]:
    """Load and validate a plugin class from ``module:Class`` or ``module.Class``."""
    if ":" in path:
        module_name, class_name = path.split(":", 1)
    elif "." in path:
        module_name, class_name = path.rsplit(".", 1)
    else:
        raise TaskError(f"{plugin_name} 載入失敗：路徑格式錯誤：{path}")

    module = import_module(module_name)
    attr = getattr(module, class_name, None)
    if attr is None or not inspect.isclass(attr):
        raise TaskError(f"{plugin_name} 載入失敗：類別不存在：{module_name}.{class_name}")
    if not issubclass(attr, base_class):
        raise TaskError(f"{plugin_name} 載入失敗：類別不相容：{class_name} 需繼承 {base_class.__name__}")
    return attr
