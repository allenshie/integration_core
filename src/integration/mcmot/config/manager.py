import yaml
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from integration.mcmot.config.schema import BaseConfig
from integration.utils.paths import get_config_root, get_core_root

class ConfigManager:
    def __init__(self, config: Optional[str] = None):
        import logging
        self._logger = logging.getLogger(__name__)
        if config:
            self.config_path = Path(config)
        else:
            config_root = get_config_root()
            self.config_path = config_root / 'data' / 'config' / 'mcmot.config.yaml'

        if not self.config_path:
            raise ValueError("Config 路徑未設定或無效")

        self._base_dir = get_config_root()
        self._registry_root = self._resolve_registry_root()
        raw_config = self._load_config(self.config_path)
        parsed_config = self._parse_cameras_config(raw_config)
        parsed_config = self._apply_camera_registry(parsed_config)
        normalized_config = self._resolve_relative_paths(parsed_config)
        self.config = BaseConfig(**normalized_config)
        for camera in self.config.cameras:
            self._logger.info("mcmot camera=%s mapping=%s", camera.camera_id, camera.coordinate_matrix_ckpt)

    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """
        載入配置文件，支援 YAML 和 JSON 格式。
        """
        if not config_path.is_file():
            raise FileNotFoundError(f"配置檔案： {config_path} 不存在或無效")
        ext = config_path.suffix.lower()
        with open(config_path, 'r', encoding='utf-8') as file:
            if ext in ['.yaml', '.yml']:
                config = yaml.safe_load(file)
            elif ext == '.json':
                config = json.load(file)
            else:
                raise ValueError("不支援的配置檔案格式，僅支援 YAML 和 JSON")
        return config

    def _parse_cameras_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        相機配置前處理
        """
        cameras = config.get("cameras")
        if isinstance(cameras, dict):
            camera_list = []
            for camera_id, camera_cfg in cameras.items():
                camera_cfg = dict(camera_cfg)
                camera_cfg["camera_id"] = camera_id
                camera_list.append(camera_cfg)
            config["cameras"] = camera_list
        return config

    def _resolve_relative_paths(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        將配置中的路徑轉換為絕對路徑，避免受工作目錄影響。
        """
        map_cfg = config.get("map")
        if isinstance(map_cfg, dict):
            image_path = map_cfg.get("image_path")
            if image_path:
                map_cfg["image_path"] = self._absolute_path(image_path)

        cameras = config.get("cameras") or []
        for camera in cameras:
            if not isinstance(camera, dict):
                continue
            for key in ("coordinate_matrix_ckpt", "ignore_polygons"):
                value = camera.get(key)
                if value:
                    camera[key] = self._absolute_path(value)
        return config

    def _apply_camera_registry(self, config: Dict[str, Any]) -> Dict[str, Any]:
        registry = self._load_camera_registry()
        if not registry:
            return config
        cameras = config.get("cameras") or []
        for camera in cameras:
            if not isinstance(camera, dict):
                continue
            camera_id = camera.get("camera_id")
            if not camera_id:
                continue
            entry = self._match_registry_entry(registry, camera_id)
            if not entry:
                continue
            mapping_file = entry.get("mapping", {}).get("file")
            if mapping_file:
                logger = getattr(self, "_logger", None)
                if logger is None:
                    import logging
                    logger = logging.getLogger(__name__)
                logger.info("mcmot 使用 registry mapping: %s", camera_id)
                camera["coordinate_matrix_ckpt"] = self._resolve_registry_path(mapping_file)
            ignore_polygons = entry.get("mcmot", {}).get("ignore_polygons")
            if ignore_polygons:
                camera["ignore_polygons"] = self._resolve_registry_path(ignore_polygons)
        return config

    def _load_camera_registry(self) -> Dict[str, Any]:
        path = self._registry_root / "config" / "cameras.yaml"
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("cameras", {}) or {}

    @staticmethod
    def _match_registry_entry(registry: Dict[str, Any], camera_id: str) -> Dict[str, Any] | None:
        direct = registry.get(camera_id)
        if direct:
            return direct
        for _, entry in registry.items():
            aliases = entry.get("aliases") or []
            if camera_id in aliases:
                return entry
        return None

    def _resolve_registry_root(self) -> Path:
        config_root = os.environ.get("CONFIG_ROOT")
        if config_root:
            return Path(config_root).expanduser().resolve()
        root = os.environ.get("SMART_WAREHOUSE_ROOT")
        if root:
            return Path(root).expanduser().resolve()
        return get_config_root()

    def _resolve_registry_path(self, value: str) -> str:
        path = Path(value)
        if path.is_absolute():
            return str(path)
        return str((self._registry_root / path).resolve())

    def _absolute_path(self, value: str) -> str:
        path = Path(value)
        if not path.is_absolute():
            path = (self._base_dir / path).resolve()
        return str(path)
