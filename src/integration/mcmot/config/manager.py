import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional
from integration.mcmot.config.schema import BaseConfig

class ConfigManager:
    def __init__(self, config: Optional[str] = None):
        if config:
            self.config_path = Path(config)
        else:
            repo_root = Path(__file__).resolve().parents[4]
            self.config_path = repo_root / 'data' / 'config' / 'mcmot.config.yaml'

        if not self.config_path:
            raise ValueError("Config 路徑未設定或無效")
            
        raw_config = self._load_config(self.config_path)
        parsed_config = self._parse_cameras_config(raw_config)
        self.config = BaseConfig(**parsed_config)

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """
        載入配置文件，支援 YAML 和 JSON 格式。
        """
        if not Path(config_path).is_file():
            raise FileNotFoundError(f"配置檔案： {config_path} 不存在或無效")
        ext = Path(config_path).suffix.lower()
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
