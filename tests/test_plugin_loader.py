from __future__ import annotations

import sys
from types import ModuleType

import pytest

from smart_workflow import TaskError

from integration.pipeline.tasks.plugin_loader import load_plugin_class


class BasePlugin:
    pass


class GoodPlugin(BasePlugin):
    pass


class BadPlugin:
    pass


@pytest.mark.parametrize("path", ["plugin_mod.GoodPlugin", "plugin_mod:GoodPlugin"])
def test_load_plugin_class_supports_dot_and_colon(monkeypatch, path: str) -> None:
    module = ModuleType("plugin_mod")
    module.GoodPlugin = GoodPlugin
    monkeypatch.setitem(sys.modules, "plugin_mod", module)

    plugin_cls = load_plugin_class(path, BasePlugin, "Demo Plugin")

    assert plugin_cls is GoodPlugin


def test_load_plugin_class_rejects_invalid_path() -> None:
    with pytest.raises(TaskError, match="Demo Plugin 載入失敗：路徑格式錯誤"):
        load_plugin_class("invalid-path", BasePlugin, "Demo Plugin")


def test_load_plugin_class_rejects_missing_class(monkeypatch) -> None:
    module = ModuleType("plugin_mod")
    monkeypatch.setitem(sys.modules, "plugin_mod", module)

    with pytest.raises(TaskError, match="Demo Plugin 載入失敗：類別不存在：plugin_mod.MissingPlugin"):
        load_plugin_class("plugin_mod.MissingPlugin", BasePlugin, "Demo Plugin")


def test_load_plugin_class_rejects_wrong_base(monkeypatch) -> None:
    module = ModuleType("plugin_mod")
    module.BadPlugin = BadPlugin
    monkeypatch.setitem(sys.modules, "plugin_mod", module)

    with pytest.raises(TaskError, match="Demo Plugin 載入失敗：類別不相容：BadPlugin"):
        load_plugin_class("plugin_mod.BadPlugin", BasePlugin, "Demo Plugin")
