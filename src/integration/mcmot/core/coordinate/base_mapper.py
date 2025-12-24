from abc import ABC, abstractmethod
from typing import Optional, Tuple
import numpy as np

class BaseMapper(ABC):
    @abstractmethod
    def transform_point(self, point: Tuple[float, float], inverse: bool = False) -> Optional[Tuple[float, float]]:
        """
        單點座標轉換

        Args:
            point: 座標點 (x, y) - 像素座標或全局座標
            inverse: False=像素→全局座標, True=全局座標→像素

        Returns:
            轉換後的座標點 (x, y) 或 None（轉換失敗）
        """
        pass

    @abstractmethod
    def transform_points(self, points: np.ndarray, inverse: bool = False) -> Optional[np.ndarray]:
        """
        批次座標轉換

        Args:
            points: 座標點陣列 Nx2 - 像素座標或全局座標
            inverse: False=像素→全局座標, True=全局座標→像素

        Returns:
            轉換後的座標點陣列 Nx2 或 None（轉換失敗）
        """
        pass