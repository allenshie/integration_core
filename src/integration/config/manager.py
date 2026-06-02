"""Generic configuration loader for integration-local YAML/JSON files."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Generic, TypeVar

import yaml


TConfig = TypeVar("TConfig")
ConfigPreprocessor = Callable[[Dict[str, Any], Path], Dict[str, Any]]


class ConfigManager(Generic[TConfig]):
    """Load a configuration file and materialize it into a config class."""

    def __init__(
        self,
        config_path: str | Path,
        config_cls: type[TConfig],
        *,
        preprocessors: tuple[ConfigPreprocessor, ...] = (),
    ) -> None:
        self.config_path = Path(config_path).expanduser().resolve()
        self.config_cls = config_cls
        self.preprocessors = preprocessors
        self._config: TConfig | None = None

    def load(self) -> TConfig:
        """Load and validate the configuration file."""
        raw_config = self._load_raw_config(self.config_path)
        normalized_config = self._apply_preprocessors(raw_config, self.config_path)
        config = self._build_config(normalized_config)
        self._config = config
        return config

    @property
    def config(self) -> TConfig:
        """Return the cached config, loading it on demand."""
        if self._config is None:
            return self.load()
        return self._config

    def reload(self) -> TConfig:
        """Reload the configuration from disk."""
        self._config = None
        return self.load()

    def _load_raw_config(self, config_path: Path) -> Dict[str, Any]:
        if not config_path.is_file():
            raise FileNotFoundError(f"配置檔案不存在：{config_path}")
        suffix = config_path.suffix.lower()
        with config_path.open("r", encoding="utf-8") as file_obj:
            if suffix in {".yaml", ".yml"}:
                raw_config = yaml.safe_load(file_obj) or {}
            elif suffix == ".json":
                raw_config = json.load(file_obj) or {}
            else:
                raise ValueError(f"不支援的配置檔格式：{config_path.suffix}")
        if not isinstance(raw_config, dict):
            raise ValueError(f"配置內容必須是物件型別：{config_path}")
        return raw_config

    def _apply_preprocessors(
        self,
        raw_config: Dict[str, Any],
        config_path: Path,
    ) -> Dict[str, Any]:
        processed = dict(raw_config)
        for preprocessor in self.preprocessors:
            processed = preprocessor(processed, config_path)
            if not isinstance(processed, dict):
                raise TypeError("Config 前處理器必須回傳 dict")
        return processed

    def _build_config(self, raw_config: Dict[str, Any]) -> TConfig:
        model_validate = getattr(self.config_cls, "model_validate", None)
        if callable(model_validate):
            return model_validate(raw_config)
        return self.config_cls(**raw_config)


__all__ = ["ConfigManager", "ConfigPreprocessor"]
