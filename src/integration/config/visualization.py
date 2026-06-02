"""Configuration model for integration-side global map visualization."""
from __future__ import annotations

from pathlib import Path
from typing import Any, List

from pydantic import BaseModel, ConfigDict, Field, field_validator

from integration.config.manager import ConfigManager
from integration.utils.paths import get_config_root


class GlobalMapConfig(BaseModel):
    """Background map definition used by the global renderer."""

    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        validate_default=True,
        str_strip_whitespace=True,
    )

    image_path: str = Field(..., description="全局地圖影像檔路徑")
    width_meters: float = Field(..., gt=0.0, description="地圖對應實際寬度（公尺）")
    height_meters: float = Field(..., gt=0.0, description="地圖對應實際高度（公尺）")

    @field_validator("image_path")
    @classmethod
    def validate_image_path(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("image_path 不能為空")
        return value.strip()


class GlobalMapRenderConfig(BaseModel):
    """Rendering options for the global map overlay."""

    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        validate_default=True,
        str_strip_whitespace=True,
    )

    mode: str = Field(default="write", description="輸出模式：write/show/both")
    output_dir: str = Field(default="output/global_map", description="輸出資料夾")
    window_name: str = Field(default="global-map", description="顯示視窗名稱")
    marker_radius: int = Field(default=6, ge=1, description="標記半徑底值")
    label_font_scale: float = Field(default=0.5, gt=0.0, description="標籤字型縮放")
    label_thickness: int = Field(default=1, ge=1, description="標籤粗細")
    show_global_id: bool = Field(default=True, description="是否顯示 global id")
    show_class_name: bool = Field(default=False, description="是否顯示 class 名稱")
    show_legend: bool = Field(default=True, description="是否顯示圖例")
    global_radius_ratio: float = Field(default=0.008, ge=0.0, description="global 標記半徑比例")
    local_radius_ratio: float = Field(default=0.004, ge=0.0, description="local 標記半徑比例")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        mode = value.strip().lower()
        if mode not in {"write", "show", "both"}:
            raise ValueError("mode 必須是 write、show 或 both")
        return mode

    @field_validator("output_dir", "window_name")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("文字欄位不能為空")
        return cleaned


class GlobalMapCameraConfig(BaseModel):
    """Camera metadata used by the integration-side renderer."""

    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        validate_default=True,
        str_strip_whitespace=True,
    )

    camera_id: str = Field(..., description="攝影機識別")
    display_name: str = Field(default="", description="顯示名稱")
    aliases: List[str] = Field(default_factory=list, description="其他可匹配的攝影機 ID")

    @field_validator("camera_id")
    @classmethod
    def validate_camera_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("camera_id 不能為空")
        return cleaned

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("aliases")
    @classmethod
    def normalize_aliases(cls, value: List[str]) -> List[str]:
        cleaned_aliases: List[str] = []
        for alias in value:
            normalized = alias.strip()
            if not normalized or normalized in cleaned_aliases:
                continue
            cleaned_aliases.append(normalized)
        return cleaned_aliases

    def model_post_init(self, __context: Any) -> None:  # pragma: no cover - pydantic hook
        if not self.display_name.strip():
            self.display_name = self.camera_id


class GlobalMapVisualizationConfig(BaseModel):
    """Whole configuration consumed by the global map renderer."""

    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        validate_default=True,
    )

    map: GlobalMapConfig = Field(..., description="地圖設定")
    render: GlobalMapRenderConfig = Field(default_factory=GlobalMapRenderConfig, description="渲染設定")
    cameras: List[GlobalMapCameraConfig] = Field(default_factory=list, description="攝影機設定清單")


def _resolve_relative_paths(raw_config: dict[str, Any], _config_path: Path) -> dict[str, Any]:
    base_dir = get_config_root()
    processed = dict(raw_config)

    map_cfg = processed.get("map")
    if isinstance(map_cfg, dict):
        image_path = map_cfg.get("image_path")
        if isinstance(image_path, str) and image_path.strip():
            path = Path(image_path.strip())
            if not path.is_absolute():
                map_cfg["image_path"] = str((base_dir / path).resolve())

    render_cfg = processed.get("render")
    if isinstance(render_cfg, dict):
        output_dir = render_cfg.get("output_dir")
        if isinstance(output_dir, str) and output_dir.strip():
            path = Path(output_dir.strip())
            if not path.is_absolute():
                render_cfg["output_dir"] = str((base_dir / path).resolve())

    return processed


def load_global_map_visualization_config(raw_path: str) -> GlobalMapVisualizationConfig:
    """Load the integration-side global map visualization config."""
    path = Path(raw_path)
    if not path.is_absolute():
        path = (get_config_root() / path).resolve()
    manager = ConfigManager(
        path,
        GlobalMapVisualizationConfig,
        preprocessors=(_resolve_relative_paths,),
    )
    return manager.load()


__all__ = [
    "GlobalMapCameraConfig",
    "GlobalMapConfig",
    "GlobalMapRenderConfig",
    "GlobalMapVisualizationConfig",
    "load_global_map_visualization_config",
]
