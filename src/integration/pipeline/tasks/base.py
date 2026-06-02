"""Task helpers for integration pipeline nodes."""
from __future__ import annotations

from typing import Any, Callable, Mapping, Type, TypeVar

from smart_workflow import BaseTask, TaskContext, TaskError, TaskResult

T = TypeVar("T")


class QuietTaskBase(BaseTask):
    """Base task that skips the default per-run start INFO log."""

    def execute(self, context: TaskContext) -> TaskResult:
        try:
            result = self.run(context)
        except TaskError as exc:
            context.report_failure(self.name, detail=str(exc))
            raise
        except Exception as exc:  # noqa: BLE001
            context.report_failure(self.name, detail=str(exc))
            raise

        result = result or TaskResult()
        context.report_success(self.name)
        return result

    def _init_plugin(
        self,
        *,
        plugin_name: str,
        loader: Callable[[str], Type[T]] | None = None,
        plugin_path: str | None = None,
        plugin_cls: Type[T] | None = None,
        default_factory: Callable[[], T] | None = None,
        init_kwargs: Mapping[str, Any] | None = None,
    ) -> T:
        """Initialize a plugin class or direct class with uniform error handling."""
        if plugin_cls is None:
            if not plugin_path:
                if default_factory is not None:
                    try:
                        return default_factory()
                    except Exception as exc:  # pylint: disable=broad-except
                        raise TaskError(f"{plugin_name} 初始化失敗：預設實作失敗（{exc}）") from exc
                raise TaskError(f"{plugin_name} 初始化失敗：未提供路徑")
            if loader is None:
                raise TaskError(f"{plugin_name} 初始化失敗：未提供載入器")
            try:
                plugin_cls = loader(plugin_path)
            except TaskError:
                raise
            except Exception as exc:  # pylint: disable=broad-except
                raise TaskError(f"{plugin_name} 載入失敗：{plugin_path}（{exc}）") from exc
            plugin_label = plugin_path
        else:
            plugin_label = getattr(plugin_cls, "__name__", plugin_name)

        kwargs = dict(init_kwargs or {})
        try:
            return plugin_cls(**kwargs)
        except TypeError:
            try:
                return plugin_cls()
            except TypeError as exc:
                raise TaskError(f"{plugin_name} 初始化失敗：{plugin_label}（{exc}）") from exc
            except Exception as exc:  # pylint: disable=broad-except
                raise TaskError(f"{plugin_name} 初始化失敗：{plugin_label}（{exc}）") from exc
        except Exception as exc:  # pylint: disable=broad-except
            raise TaskError(f"{plugin_name} 初始化失敗：{plugin_label}（{exc}）") from exc
