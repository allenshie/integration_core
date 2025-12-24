"""Rendering helpers for drawing MC-MOT results on the global warehouse map."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import cv2  # type: ignore[import]
import numpy as np

from integration.config.settings import GlobalMapVisualizationConfig
from integration.mcmot.config.schema import CameraConfig, MapConfig


@dataclass
class OverlayResult:
    image_path: Path | None
    rendered: np.ndarray | None


_DEFAULT_CLASS_PALETTE: Dict[str, tuple[int, int, int]] = {
    "person": (0, 255, 0),
    "stacker": (0, 165, 255),
    "forklift": (0, 128, 255),
}

_CAMERA_COLOR_PALETTE: Sequence[tuple[int, int, int]] = (
    (0, 128, 255),
    (255, 128, 0),
    (128, 0, 255),
    (0, 255, 255),
    (255, 0, 128),
    (0, 255, 128),
    (255, 255, 0),
    (255, 0, 0),
    (0, 0, 255),
)


class GlobalMapRenderer:
    """Centralized renderer that overlays global/local objects onto the warehouse map."""

    def __init__(
        self,
        map_cfg: MapConfig,
        vis_cfg: GlobalMapVisualizationConfig,
        *,
        logger,
        camera_configs: Sequence[CameraConfig] | None = None,
    ) -> None:
        self._map_cfg = map_cfg
        self._vis_cfg = vis_cfg
        self._logger = logger
        self._camera_cfgs = list(camera_configs or [])
        self._allowed_cameras = set(vis_cfg.local_camera_ids)
        self._base_canvas: np.ndarray | None = None
        self._image_mtime: float | None = None
        self._camera_colors: Dict[str, tuple[int, int, int]] = {}
        self._camera_alias_lookup: Dict[str, str] = {}
        self._legend_entries: List[Tuple[str, str, tuple[int, int, int]]] = []
        self._min_map_dim = min(self._map_cfg.pixel_width, self._map_cfg.pixel_height)
        self._global_radius, self._local_radius = self._compute_radii()
        self._global_font_scale, self._global_label_thickness = self._compute_font_params(
            self._global_radius,
        )
        self._local_font_scale, self._local_label_thickness = self._compute_font_params(
            self._local_radius,
            scale_bias=0.85,
        )
        self._build_camera_color_map()
        self._palette_cursor = len(self._legend_entries)

    def render(
        self,
        global_objects: Iterable[Mapping],
        local_objects: Iterable[Mapping],
    ) -> OverlayResult | None:
        if not self._vis_cfg.enabled:
            return None
        canvas = self._load_base_canvas()
        if canvas is None:
            return None
        rendered = canvas.copy()

        global_list = list(global_objects)
        local_list = list(local_objects)

        global_count = self._draw_global_objects(rendered, global_list)
        local_payload = self._prepare_local_overlay_objects(local_list, global_list)
        local_count, used_cameras = self._draw_local_objects(rendered, local_payload)

        if self._vis_cfg.show_legend:
            self._draw_legend(rendered, focus_cameras=used_cameras)

        saved_path = self._finalize(rendered)
        if saved_path is None and global_count == 0 and local_count == 0:
            self._logger.debug("全局地圖沒有可視化的物件")
        return OverlayResult(image_path=saved_path, rendered=rendered)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_base_canvas(self) -> np.ndarray | None:
        image_path = self._map_cfg.image_path
        if not image_path:
            self._logger.debug("全局地圖未設定影像路徑，略過可視化")
            return None
        path = Path(image_path)
        if not path.exists():
            self._logger.warning("找不到全局地圖影像：%s", path)
            return None
        mtime = path.stat().st_mtime
        if self._base_canvas is None or self._image_mtime != mtime:
            canvas = cv2.imread(str(path))
            if canvas is None:
                self._logger.warning("無法載入全局地圖影像：%s", path)
                return None
            self._base_canvas = canvas
            self._image_mtime = mtime
        return self._base_canvas

    def _compute_radii(self) -> tuple[int, int]:
        min_dim = max(1, self._min_map_dim)
        global_dynamic = int(min_dim * max(0.0, self._vis_cfg.global_radius_ratio))
        global_radius = max(self._vis_cfg.marker_radius, global_dynamic, 4)
        local_dynamic = int(min_dim * max(0.0, self._vis_cfg.local_radius_ratio))
        local_radius = max(2, min(global_radius - 2, local_dynamic or global_radius // 2))
        return global_radius, max(2, local_radius)

    def _draw_global_objects(
        self,
        canvas: np.ndarray,
        global_objects: Iterable[Mapping],
    ) -> int:
        count = 0
        for obj in global_objects:
            coords = self._extract_global_xy(obj)
            if coords is None:
                continue
            x, y = int(round(coords[0])), int(round(coords[1]))
            color = self._color_for_global(obj.get("class_name"))
            cv2.circle(canvas, (x, y), self._global_radius, color, thickness=-1)
            label_parts: List[str] = []
            if self._vis_cfg.show_global_id and obj.get("global_id") is not None:
                label_parts.append(str(obj.get("global_id")))
            if self._vis_cfg.show_class_name and obj.get("class_name"):
                label_parts.append(str(obj.get("class_name")))
            if label_parts:
                cv2.putText(
                    canvas,
                    "|".join(label_parts),
                    (x + self._global_radius + 4, y - 4),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    self._global_font_scale,
                    color,
                    self._global_label_thickness,
                    lineType=cv2.LINE_AA,
                )
            count += 1
        return count

    def _prepare_local_overlay_objects(
        self,
        local_objects: Iterable[Mapping],
        global_objects: Iterable[Mapping],
    ) -> List[Dict]:
        global_lookup = {
            obj.get("global_id"): obj for obj in global_objects if obj.get("global_id") is not None
        }
        prepared: List[Dict] = []
        for item in local_objects:
            camera_id = item.get("camera_id")
            if not camera_id:
                continue
            canonical_id = self._camera_alias_lookup.get(camera_id, camera_id)
            if self._allowed_cameras:
                if camera_id not in self._allowed_cameras and canonical_id not in self._allowed_cameras:
                    continue
            coords = self._coerce_point(item.get("global_position"))
            if coords is None:
                continue
            global_id = item.get("global_id")
            distance_m = None
            if global_id is not None:
                ref_obj = global_lookup.get(global_id)
                if ref_obj is not None:
                    ref_xy = self._extract_global_xy(ref_obj)
                    if ref_xy is not None:
                        dx = coords[0] - ref_xy[0]
                        dy = coords[1] - ref_xy[1]
                        distance_m = self._map_cfg.distance_in_meters(dx, dy)
            prepared.append(
                {
                    "camera_id": camera_id,
                    "canonical_id": canonical_id,
                    "local_id": item.get("local_id"),
                    "global_id": global_id,
                    "point": coords,
                    "distance_m": distance_m,
                }
            )
        return prepared

    def _draw_local_objects(
        self,
        canvas: np.ndarray,
        local_objects: List[Dict],
    ) -> tuple[int, set[str]]:
        rendered = 0
        used_cameras: set[str] = set()
        for obj in local_objects:
            point = obj["point"]
            color = self._camera_colors.get(obj["camera_id"]) or self._camera_colors.get(
                obj["canonical_id"],
            )
            if color is None:
                color = self._assign_fallback_color(obj["camera_id"])
            x = int(round(point[0]))
            y = int(round(point[1]))
            cv2.circle(canvas, (x, y), self._local_radius, color, thickness=-1)
            label_parts: List[str] = []
            if obj.get("local_id") is not None:
                label_parts.append(f"l_{obj.get('local_id')}")
            if obj.get("global_id") is not None:
                label_parts.append(f"g_{obj.get('global_id')}")
            distance = obj.get("distance_m")
            if distance is not None:
                label_parts.append(f"{distance:.2f}M")
            if label_parts:
                cv2.putText(
                    canvas,
                    " | ".join(label_parts),
                    (x + self._local_radius + 4, y - 4),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    self._local_font_scale,
                    color,
                    self._local_label_thickness,
                    lineType=cv2.LINE_AA,
                )
            rendered += 1
            used_cameras.add(obj["canonical_id"])
        if rendered == 0:
            self._logger.debug("沒有符合條件的 local 物件可視化")
        return rendered, used_cameras

    def _draw_legend(
        self,
        canvas: np.ndarray,
        *,
        focus_cameras: set[str],
    ) -> None:
        sections: List[Tuple[str, str | None, tuple[int, int, int] | None]] = []
        global_palette = self._build_global_legend()
        if global_palette:
            sections.append(("title", "Global Objects", None))
            for class_name, color in global_palette:
                sections.append(("item", class_name, color))
        camera_entries = self._build_camera_legend(focus_cameras)
        if camera_entries:
            if sections:
                sections.append(("spacer", None, None))
            sections.append(("title", "Cameras", None))
            sections.extend(camera_entries)
        if not sections:
            return
        padding = 10
        line_height = 22
        item_count = len([entry for entry in sections if entry[0] != "spacer"])
        width = 240
        height = padding * 2 + line_height * item_count
        overlay = canvas.copy()
        top_left = (padding, padding)
        bottom_right = (padding + width, padding + height)
        cv2.rectangle(overlay, top_left, bottom_right, (30, 30, 30), thickness=-1)
        cv2.addWeighted(overlay, 0.4, canvas, 0.6, 0, canvas)
        y = padding + line_height - 6
        for kind, display_name, color in sections:
            if kind == "spacer":
                y += line_height // 2
                continue
            if kind == "title":
                cv2.putText(
                    canvas,
                    display_name or "",
                    (padding + 8, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    1,
                    lineType=cv2.LINE_AA,
                )
                y += line_height
                continue
            if color is None or display_name is None:
                continue
            cv2.rectangle(
                canvas,
                (padding + 8, y - 12),
                (padding + 28, y + 4),
                color,
                thickness=-1,
            )
            cv2.putText(
                canvas,
                display_name,
                (padding + 34, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                1,
                lineType=cv2.LINE_AA,
            )
            y += line_height

    def _finalize(self, rendered: np.ndarray) -> Path | None:
        saved_path: Path | None = None
        mode = self._vis_cfg.mode
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        if mode in {"write", "both"}:
            output_dir = Path(self._vis_cfg.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            saved_path = output_dir / f"global_map_{timestamp}.png"
            cv2.imwrite(str(saved_path), rendered)
            self._logger.debug("已輸出全局地圖快照：%s", saved_path)

        if mode in {"show", "both"}:
            try:
                cv2.imshow(self._vis_cfg.window_name, rendered)
                cv2.waitKey(1)
            except cv2.error as exc:  # pragma: no cover
                self._logger.warning("無法顯示全局地圖視窗：%s", exc)
        return saved_path

    def _build_camera_color_map(self) -> None:
        palette_index = 0
        for camera in self._camera_cfgs:
            color = self._parse_color(camera.color_hex)
            if color is None:
                color = _CAMERA_COLOR_PALETTE[palette_index % len(_CAMERA_COLOR_PALETTE)]
                palette_index += 1
            display_name = camera.name or camera.camera_id
            self._legend_entries.append((camera.camera_id, display_name, color))
            self._camera_colors[camera.camera_id] = color
            self._camera_alias_lookup[camera.camera_id] = camera.camera_id
            edge_id = camera.edge_id or camera.camera_id
            self._camera_colors[edge_id] = color
            self._camera_alias_lookup[edge_id] = camera.camera_id

    def _color_for_global(self, class_name: str | None) -> tuple[int, int, int]:
        if class_name and class_name in self._vis_cfg.class_colors:
            return self._vis_cfg.class_colors[class_name]
        if self._vis_cfg.global_color is not None:
            return self._vis_cfg.global_color
        if class_name and class_name in _DEFAULT_CLASS_PALETTE:
            return _DEFAULT_CLASS_PALETTE[class_name]
        return (255, 255, 255)

    def _assign_fallback_color(self, camera_id: str) -> tuple[int, int, int]:
        color = _CAMERA_COLOR_PALETTE[self._palette_cursor % len(_CAMERA_COLOR_PALETTE)]
        self._palette_cursor += 1
        self._camera_colors[camera_id] = color
        self._camera_alias_lookup[camera_id] = camera_id
        self._legend_entries.append((camera_id, camera_id, color))
        return color

    @staticmethod
    def _coerce_point(value: Mapping | None) -> tuple[float, float] | None:
        if not value:
            return None
        x = value.get("x")
        y = value.get("y")
        if x is None or y is None:
            return None
        try:
            return float(x), float(y)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_global_xy(obj: Mapping) -> tuple[float, float] | None:
        trajectory = obj.get("trajectory")
        if not trajectory:
            return None
        last = trajectory[-1]
        if isinstance(last, Mapping):
            x = last.get("x")
            y = last.get("y")
        elif isinstance(last, (tuple, list)) and len(last) >= 3:
            x = last[1]
            y = last[2]
        else:
            return None
        if x is None or y is None:
            return None
        try:
            return float(x), float(y)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_color(value: str | None) -> tuple[int, int, int] | None:
        if not value:
            return None
        hex_value = value.strip().lstrip("#")
        if len(hex_value) != 6:
            return None
        try:
            r = int(hex_value[0:2], 16)
            g = int(hex_value[2:4], 16)
            b = int(hex_value[4:6], 16)
        except ValueError:
            return None
        return (b, g, r)

    def _compute_font_params(
        self,
        radius: int,
        *,
        scale_bias: float = 1.0,
    ) -> tuple[float, int]:
        base_scale = max(0.3, self._vis_cfg.label_font_scale)
        dynamic_scale = max(0.3, radius / 14.0)
        scale = max(base_scale, dynamic_scale * scale_bias)
        base_thickness = max(1, self._vis_cfg.label_thickness)
        dynamic_thickness = max(1, int(round(radius / 8)))
        return scale, max(base_thickness, dynamic_thickness)

    def _build_global_legend(self) -> List[Tuple[str, tuple[int, int, int]]]:
        palette: List[Tuple[str, tuple[int, int, int]]] = []
        source = self._vis_cfg.class_colors or _DEFAULT_CLASS_PALETTE
        for class_name, color in source.items():
            palette.append((class_name, color))
        if not palette:
            palette.append(("Global", self._color_for_global(None)))
        return palette

    def _build_camera_legend(self, focus_cameras: set[str]) -> List[Tuple[str, str, tuple[int, int, int]]]:
        # Legend 需完整顯示所有 camera/canonical 顏色，避免因當前畫面無物件而缺漏
        entries: List[Tuple[str, str, tuple[int, int, int]]] = []
        for camera_id, display_name, color in self._legend_entries:
            entries.append(("item", display_name, color))
        return entries


__all__ = ["OverlayResult", "GlobalMapRenderer"]
