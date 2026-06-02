from __future__ import annotations

import pytest

from smart_workflow import TaskError, TaskResult

from integration.pipeline.tasks.base import QuietTaskBase


class DummyPlugin:
    def __init__(self, value: int | None = None) -> None:
        self.value = value


class DummyTask(QuietTaskBase):
    name = "dummy"

    def run(self, context):  # noqa: ANN001
        return TaskResult(status="ok")


def test_init_plugin_with_direct_class() -> None:
    task = DummyTask()

    plugin = task._init_plugin(
        plugin_name="Dummy Plugin",
        plugin_cls=DummyPlugin,
        init_kwargs={"value": 7},
    )

    assert isinstance(plugin, DummyPlugin)
    assert plugin.value == 7


def test_init_plugin_with_loader_path() -> None:
    task = DummyTask()

    plugin = task._init_plugin(
        plugin_name="Dummy Plugin",
        loader=lambda path: DummyPlugin,  # noqa: ARG005
        plugin_path="example.plugins:DummyPlugin",
        init_kwargs={"value": 8},
    )

    assert isinstance(plugin, DummyPlugin)
    assert plugin.value == 8


def test_init_plugin_with_default_factory() -> None:
    task = DummyTask()

    plugin = task._init_plugin(
        plugin_name="Dummy Plugin",
        default_factory=lambda: DummyPlugin(9),
    )

    assert isinstance(plugin, DummyPlugin)
    assert plugin.value == 9


def test_init_plugin_rejects_missing_path() -> None:
    task = DummyTask()

    with pytest.raises(TaskError, match="Dummy Plugin 初始化失敗：未提供路徑"):
        task._init_plugin(plugin_name="Dummy Plugin")


def test_init_plugin_rejects_missing_loader() -> None:
    task = DummyTask()

    with pytest.raises(TaskError, match="Dummy Plugin 初始化失敗：未提供載入器"):
        task._init_plugin(plugin_name="Dummy Plugin", plugin_path="example.plugins:DummyPlugin")
