"""
TPS 座標映射器
使用預計算的 NPZ 映射表進行座標轉換
"""

import numpy as np
import cv2
from pathlib import Path

from .base_mapper import BaseMapper
from integration.mcmot.utils.logger import get_logger

class TPSMapper(BaseMapper):
    """
    TPS 座標映射器
    載入 .npz 映射表，進行像素座標 ↔ 全局座標的轉換
    """

    def __init__(self, mapping_file):
        """
        Args:
            mapping_file: NPZ 映射表檔案路徑
        """
        self.mapping_file = Path(mapping_file)

        self.logger = get_logger(
            name="tps_mapper",
            log_file="coordinate_transformer"
        )

        if not self.mapping_file.exists():
            raise FileNotFoundError(f"找不到映射表: {mapping_file}")

        # 載入映射表
        data = np.load(self.mapping_file)

        # 正向映射 (像素 → 全局)
        self.map_x = data['map_x']
        self.map_y = data['map_y']

        # 元數據
        self.width = int(data['width'])
        self.height = int(data['height'])
        self.sparse_scale = int(data['sparse_scale'])

        # 如果是稀疏映射，放大到完整解析度
        if self.sparse_scale > 1:
            self.map_x_full = cv2.resize(
                self.map_x.astype(np.float32),
                (self.width, self.height),
                interpolation=cv2.INTER_LINEAR
            )
            self.map_y_full = cv2.resize(
                self.map_y.astype(np.float32),
                (self.width, self.height),
                interpolation=cv2.INTER_LINEAR
            )
        else:
            self.map_x_full = self.map_x.astype(np.float32) if self.map_x.dtype == np.float16 else self.map_x
            self.map_y_full = self.map_y.astype(np.float32) if self.map_y.dtype == np.float16 else self.map_y

        # 反向映射 (全局 → 像素) - 延遲建立
        self.inverse_map_u = None
        self.inverse_map_v = None
        self.global_bounds = None

        self.logger.info(f"✓ 映射表已載入: {mapping_file}")
        self.logger.info(f"  解析度: {self.width} x {self.height}")

    def transform_point(self, point, inverse=False):
        """
        單點座標轉換

        Args:
            point: 座標點 tuple (x, y) - 像素座標或全局座標
            inverse: False=像素→全局座標, True=全局座標→像素

        Returns:
            轉換後的座標點 (x, y) 或 None（轉換失敗）
        """
        u, v = point[0], point[1]
        
        if not inverse:
            # 正向: 像素 → 全局
            if not (0 <= v < self.height and 0 <= u < self.width):
                return None

            map_x = self.map_x_full[int(v), int(u)]
            map_y = self.map_y_full[int(v), int(u)]
            return (float(map_x), float(map_y))

        else:
            # 反向轉換: 全局 → 像素（目前未實作）
            raise NotImplementedError(
                "TPSMapper 的反向轉換（全局→像素）目前尚未實作。"
                "如需此功能，請使用 HomographyMapper 或實作反向映射表。"
            )

    def transform_points(self, points, inverse=False):
        """
        批次座標轉換

        Args:
            points: 座標點陣列 Nx2 numpy array - 像素座標或全局座標
            inverse: False=像素→全局座標, True=全局座標→像素

        Returns:
            轉換後的座標點陣列 Nx2 numpy array 或 None（轉換失敗）
        """
        if not inverse:
            # 正向: 像素 → 全局（批次處理）
            points = np.asarray(points)
            if points.ndim != 2 or points.shape[1] != 2:
                raise ValueError(f"points 必須是 Nx2 陣列，但得到形狀: {points.shape}")
            
            result = np.zeros_like(points, dtype=np.float32)
            
            for i, (u, v) in enumerate(points):
                # 檢查邊界
                if not (0 <= v < self.height and 0 <= u < self.width):
                    # 超出邊界的點設為 NaN
                    result[i] = [np.nan, np.nan]
                    continue
                
                # 查表取得全局座標
                map_x = self.map_x_full[int(v), int(u)]
                map_y = self.map_y_full[int(v), int(u)]
                result[i] = [map_x, map_y]
            
            return result
        
        else:
            # 反向轉換: 全局 → 像素（目前未實作）
            raise NotImplementedError(
                "TPSMapper 的反向轉換（全局→像素）目前尚未實作。"
                "如需此功能，請使用 HomographyMapper 或實作反向映射表。"
            )

    def _fill_holes(self, data):
        """填補 NaN 空洞"""
        mask = np.isnan(data)
        if not np.any(mask):
            return data

        # 使用 cv2.inpaint 填補
        valid_mask = ~mask
        if np.any(valid_mask):
            # 正規化到 0-255
            valid_data = data[valid_mask]
            data_min, data_max = valid_data.min(), valid_data.max()

            # 避免除以零
            if data_max == data_min:
                return data

            # 只對有效區域進行正規化
            normalized = np.zeros_like(data, dtype=np.uint8)
            normalized[valid_mask] = ((valid_data - data_min) / (data_max - data_min) * 255).astype(np.uint8)

            # 填補
            inpainted = cv2.inpaint(normalized, mask.astype(np.uint8), 3, cv2.INPAINT_NS)

            # 反正規化
            result = inpainted.astype(np.float32) / 255 * (data_max - data_min) + data_min
            return result

        return data
        
    def get_info(self):
        """獲取映射表資訊"""
        mem_size = (self.map_x_full.nbytes + self.map_y_full.nbytes) / (1024**2)

        info = {
            'width': self.width,
            'height': self.height,
            'sparse_scale': self.sparse_scale,
            'memory_mb': mem_size,
            'has_inverse': self.inverse_map_u is not None
        }

        return info
