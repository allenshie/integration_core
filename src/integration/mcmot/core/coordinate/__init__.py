"""
座標轉換模組

提供多種座標轉換方式：
- HomographyMapper: 使用單應性矩陣進行座標轉換
- TPSMapper: 使用薄板樣條 (TPS) 映射表進行座標轉換
- CoordinateTransformer: 統一的座標轉換介面，支援多攝影機系統
"""

from .base_mapper import BaseMapper
from .homography_mapper import HomographyMapper
from .tps_mapper import TPSMapper
from .coordinate_transformer import CoordinateTransformer

__all__ = [
    'BaseMapper',
    'HomographyMapper',
    'TPSMapper',
    'CoordinateTransformer',
]

