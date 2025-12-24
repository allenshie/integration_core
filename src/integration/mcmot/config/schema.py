from __future__ import annotations

from typing import List, Optional
import math
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class TrackingConfig(BaseModel):
    """追蹤配置模型，目前僅保留可追蹤類別設定。"""

    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        validate_default=True,
    )

    trackable_classes: List[str] = Field(default_factory=lambda: ["person"], description="可追蹤的物件類別列表")
    match_threshold: float = Field(default=1.0, gt=0.0, description="成本需低於此值才視為匹配成功")
    max_traj_loss: float = Field(default=1000.0, gt=0.0, description="軌跡損失正規化上限（像素）")
    distance_threshold_m: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="若設定，local/global 物件須在此公尺範圍內才允許匹配",
    )

    @field_validator("trackable_classes")
    @classmethod
    def validate_trackable_classes(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("可追蹤的物件類別不能為空")
        return value


class SystemConfig(BaseModel):
    """系統相關設定，目前僅關注座標轉換模式。"""

    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        validate_default=True,
        str_strip_whitespace=True,
    )

    coordinate_transform_mode: str = Field(default="tps", description="座標轉換模式 (tps/homography)")

    @field_validator("coordinate_transform_mode")
    @classmethod
    def validate_coordinate_transform_mode(cls, value: str) -> str:
        mode = value.strip().lower()
        if mode not in {"tps", "homography"}:
            raise ValueError("座標轉換模式必須是 'tps' 或 'homography'")
        return mode


class MapConfig(BaseModel):
    """全局地圖定義與像素/公尺換算。"""

    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        validate_default=True,
    )

    image_path: Optional[str] = Field(default=None, description="全局地圖影像檔（選填）")
    pixel_width: int = Field(..., gt=0, description="地圖影像寬度（像素）")
    pixel_height: int = Field(..., gt=0, description="地圖影像高度（像素）")
    width_meters: float = Field(..., gt=0.0, description="地圖對應實際寬度（公尺）")
    height_meters: float = Field(..., gt=0.0, description="地圖對應實際高度（公尺）")

    @property
    def meters_per_pixel_x(self) -> float:
        return self.width_meters / float(self.pixel_width)

    @property
    def meters_per_pixel_y(self) -> float:
        return self.height_meters / float(self.pixel_height)

    def distance_in_meters(self, dx_pixels: float, dy_pixels: float) -> float:
        scale_x = self.meters_per_pixel_x
        scale_y = self.meters_per_pixel_y
        return math.hypot(dx_pixels * scale_x, dy_pixels * scale_y)

class CameraConfig(BaseModel):
    """攝影機配置：描述 edge camera 與全域地圖之間的對應。"""

    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        validate_default=True,
    )

    camera_id: str = Field(..., description="整合端使用的攝影機識別")
    edge_id: Optional[str] = Field(default=None, description="edge 事件中的 camera_id，預設與 camera_id 相同")
    name: str = Field(default="", description="攝影機名稱（可選）")
    zone_id: Optional[str] = Field(default=None, description="對應倉儲區域識別（可選）")
    enabled: bool = Field(default=True, description="是否啟用此攝影機")
    coordinate_matrix_ckpt: str = Field(..., description="座標轉換矩陣（.npz/.npy）檔案路徑")
    ignore_polygons: Optional[str] = Field(default=None, description="忽略區域 .npy 檔案路徑（可選）")
    color_hex: Optional[str] = Field(default=None, description="可視化時使用的自訂顏色（#RRGGBB）")

    @field_validator("camera_id")
    @classmethod
    def validate_camera_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("攝影機 ID 不能為空")
        return value.strip()

    @field_validator("coordinate_matrix_ckpt")
    @classmethod
    def validate_coordinate_matrix_ckpt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("座標轉換矩陣檔案路徑不能為空")
        return value.strip()

    @field_validator("color_hex")
    @classmethod
    def validate_color_hex(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip()
        if cleaned.startswith("#"):
            cleaned = cleaned[1:]
        if cleaned == "":
            return None
        if len(cleaned) != 6:
            raise ValueError("color_hex 必須為 6 碼十六進位顏色")
        try:
            int(cleaned, 16)
        except ValueError as exc:
            raise ValueError("color_hex 不是有效的十六進位顏色") from exc
        return "#" + cleaned.upper()

class BaseConfig(BaseModel):
    """全域配置模型，包含系統、追蹤設定與各攝影機映射。"""

    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
    )

    version: str = Field(default="1.0.0", description="配置版本")
    name: str = Field(default="MCMOT Configuration", description="配置名稱")
    system: SystemConfig = Field(default_factory=SystemConfig, description="系統配置")
    tracking: TrackingConfig = Field(default_factory=TrackingConfig, description="追蹤配置")
    map: Optional[MapConfig] = Field(default=None, description="全局地圖設定（選填）")
    cameras: List[CameraConfig] = Field(default_factory=list, description="攝影機配置")

    @model_validator(mode="after")
    def validate_cameras(self) -> "BaseConfig":
        enabled_cameras = [cam for cam in self.cameras if cam.enabled]
        if not enabled_cameras:
            raise ValueError("至少需要一個啟用的攝影機")
        for camera in self.cameras:
            if not camera.edge_id:
                camera.edge_id = camera.camera_id
        return self

    def get_enabled_camera(self) -> List[CameraConfig]:
        return [cam for cam in self.cameras if cam.enabled]

    def get_camera_by_edge_id(self, edge_id: str) -> CameraConfig:
        camera = next(
            (cam for cam in self.cameras if cam.enabled and (cam.edge_id == edge_id or cam.camera_id == edge_id)),
            None,
        )
        if camera is None:
            raise ValueError(f"找不到 edge camera '{edge_id}' 的對應設定")
        return camera
    
