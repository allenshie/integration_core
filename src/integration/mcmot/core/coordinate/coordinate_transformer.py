import numpy as np
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from integration.mcmot.utils.logger import get_logger

from .base_mapper import BaseMapper
from .homography_mapper import HomographyMapper
from .tps_mapper import TPSMapper


class CoordinateTransformer:
    """
    統一的座標轉換器
    處理多攝影機系統的座標轉換：像素座標 ↔ 全局座標
    
    支援兩種轉換模式：
    1. Homography（單應性矩陣）- 使用 .npy 矩陣檔案
    2. TPS（薄板樣條）- 使用 .npz 映射表檔案
    
    轉換模式由配置檔案中的 system.coordinate_transform_mode 指定
    """
    
    def __init__(self, config):
        """
        初始化座標轉換器
        
        Args:
            config: 配置物件，包含系統設定和攝影機配置
        """
        self.logger = get_logger(
            name="coordinate_transformer",
            log_file="coordinate_transformer"
        )
        self.config = config
        self.mappers: Dict[str, BaseMapper] = {}
        
        # 取得座標轉換模式（tps 或 homography）
        self.transform_mode = config.system.coordinate_transform_mode
        self.logger.info(f"座標轉換模式: {self.transform_mode}")
        
        self._initialize_mappers()
    
    def _initialize_mappers(self) -> None:
        """初始化各攝影機的座標映射器"""
        cameras = self.config.cameras
        self.logger.info(f"初始化 {len(cameras)} 個攝影機的座標映射器 (模式: {self.transform_mode})")
        
        for camera in cameras:
            self.logger.info(
                f"處理攝影機 {camera.camera_id}, "
                f"啟用狀態: {camera.enabled}, "
                f"座標矩陣路徑: {camera.coordinate_matrix_ckpt}"
            )
            
            if not camera.enabled:
                self.logger.warning(f"攝影機 {camera.camera_id} 已停用")
                continue
            
            if not camera.coordinate_matrix_ckpt:
                self.logger.warning(f"攝影機 {camera.camera_id} 沒有座標矩陣路徑")
                continue
            
            try:
                matrix_path = Path(camera.coordinate_matrix_ckpt)
                
                if not matrix_path.exists():
                    self.logger.warning(f"座標矩陣檔案不存在: {matrix_path}")
                    continue
                
                # 根據模式建立對應的 mapper
                mapper = self._create_mapper(str(matrix_path))
                
                if mapper is not None:
                    self.mappers[camera.camera_id] = mapper
                    self.logger.info(
                        f"成功載入攝影機 {camera.camera_id} 的座標映射器 "
                        f"({self.transform_mode})"
                    )
                
            except Exception as e:
                self.logger.error(
                    f"載入攝影機 {camera.camera_id} 的座標映射器失敗: {e}",
                    exc_info=True
                )
        
        self.logger.info(f"已初始化 {len(self.mappers)} 個座標映射器")
    
    def _create_mapper(self, matrix_path: str) -> Optional[BaseMapper]:
        """
        根據轉換模式建立對應的 mapper
        
        Args:
            matrix_path: 座標矩陣檔案路徑
            
        Returns:
            BaseMapper 實例或 None
        """
        if self.transform_mode == "homography":
            # Homography 模式：載入 .npy 矩陣檔案
            mapper = HomographyMapper()
            mapper.load_homography(matrix_path)
            return mapper
            
        elif self.transform_mode == "tps":
            # TPS 模式：載入 .npz 映射表檔案
            mapper = TPSMapper(matrix_path)
            return mapper
            
        else:
            self.logger.error(f"不支援的座標轉換模式: {self.transform_mode}")
            return None
    
    # ===== 軌跡轉換方法 =====
    
    def transform_local_to_global(self, camera_id: str, objects: List[Dict]) -> bool:
        """
        將攝影機局部座標轉換為全域座標
        
        Args:
            camera_id: 攝影機 ID
            objects: 包含局部軌跡的偵測物件清單，每個物件應包含 'local_trajectory' 欄位
            
        Returns:
            True 如果轉換成功，False 否則
        """
        if camera_id not in self.mappers:
            self.logger.warning(f"找不到攝影機 {camera_id} 的座標映射器")
            return False
        
        mapper = self.mappers[camera_id]
        
        try:
            for obj in objects:
                local_trajectory = obj.get('local_trajectory', [])
                if local_trajectory:
                    global_trajectory = self._transform_trajectory(mapper, local_trajectory)
                    obj['global_trajectory'] = global_trajectory  # 已經是 list，不需要 tolist()
            return True
            
        except Exception as e:
            self.logger.error(f"轉換攝影機 {camera_id} 座標時發生錯誤: {e}", exc_info=True)
            return False
    
    def _transform_trajectory(self, mapper: BaseMapper, local_trajectory: List) -> List:
        """
        將單一軌跡從局部座標轉換為全域座標

        Args:
            mapper: 座標映射器
            local_trajectory: 局部軌跡點 [[timestamp, x, y], ...]

        Returns:
            全域軌跡列表 [[timestamp, global_x, global_y], ...]
        """
        # 分離時間戳與座標（不使用 numpy array，因為 timestamp 可能是 datetime）
        timestamps = [point[0] for point in local_trajectory]
        xy_coords = np.array([[point[1], point[2]] for point in local_trajectory])

        # 轉換座標
        global_coords = mapper.transform_points(xy_coords, inverse=False)

        # 合併時間戳與全域座標，保持為 list
        global_trajectory = [[timestamps[i], global_coords[i][0], global_coords[i][1]]
                            for i in range(len(timestamps))]

        return global_trajectory
    
    # ===== 單點轉換方法 =====
    
    def transform_point_local_to_global(
        self, 
        camera_id: str, 
        point: Tuple[float, float]
    ) -> Optional[Tuple[float, float]]:
        """
        將單點從局部座標轉換為全域座標
        
        Args:
            camera_id: 攝影機 ID
            point: 局部座標點 (x, y)
            
        Returns:
            全域座標點 (x, y) 或 None（如果轉換失敗）
        """
        if camera_id not in self.mappers:
            self.logger.warning(f"找不到攝影機 {camera_id} 的座標映射器")
            return None
        
        try:
            mapper = self.mappers[camera_id]
            global_point = mapper.transform_points(np.array([point]), inverse=False)[0]
            return tuple(global_point)
            
        except Exception as e:
            self.logger.error(
                f"轉換攝影機 {camera_id} 點座標時發生錯誤: {e}",
                exc_info=True
            )
            return None
    
    def transform_point_global_to_local(
        self, 
        camera_id: str, 
        point: Tuple[float, float]
    ) -> Optional[Tuple[float, float]]:
        """
        將單點從全域座標轉換為局部座標（反向轉換）
        
        Args:
            camera_id: 攝影機 ID
            point: 全域座標點 (x, y)
            
        Returns:
            局部座標點 (x, y) 或 None（如果轉換失敗）
        """
        if camera_id not in self.mappers:
            self.logger.warning(f"找不到攝影機 {camera_id} 的座標映射器")
            return None
        
        try:
            mapper = self.mappers[camera_id]
            local_point = mapper.transform_points(np.array([point]), inverse=True)[0]
            return tuple(local_point)
            
        except Exception as e:
            self.logger.error(
                f"反向轉換攝影機 {camera_id} 點座標時發生錯誤: {e}",
                exc_info=True
            )
            return None
    
    # ===== 批次轉換方法 =====
    
    def transform_points_local_to_global_batch(
        self, 
        camera_id: str, 
        points: List[Tuple[float, float]]
    ) -> Optional[np.ndarray]:
        """
        批次將多點從局部座標轉換為全域座標
        
        Args:
            camera_id: 攝影機 ID
            points: 局部座標點清單 [(x1, y1), (x2, y2), ...]
            
        Returns:
            全域座標點陣列 Nx2 或 None（如果轉換失敗）
        """
        if camera_id not in self.mappers:
            self.logger.warning(f"找不到攝影機 {camera_id} 的座標映射器")
            return None
        
        try:
            mapper = self.mappers[camera_id]
            points_array = np.array(points)
            global_points = mapper.transform_points(points_array, inverse=False)
            return global_points
            
        except Exception as e:
            self.logger.error(
                f"批次轉換攝影機 {camera_id} 點座標時發生錯誤: {e}",
                exc_info=True
            )
            return None
    
    def transform_points_global_to_local_batch(
        self, 
        camera_id: str, 
        points: List[Tuple[float, float]]
    ) -> Optional[np.ndarray]:
        """
        批次將多點從全域座標轉換為局部座標（反向轉換）
        
        Args:
            camera_id: 攝影機 ID
            points: 全域座標點清單 [(x1, y1), (x2, y2), ...]
            
        Returns:
            局部座標點陣列 Nx2 或 None（如果轉換失敗）
        """
        if camera_id not in self.mappers:
            self.logger.warning(f"找不到攝影機 {camera_id} 的座標映射器")
            return None
        
        try:
            mapper = self.mappers[camera_id]
            points_array = np.array(points)
            local_points = mapper.transform_points(points_array, inverse=True)
            return local_points
            
        except Exception as e:
            self.logger.error(
                f"批次反向轉換攝影機 {camera_id} 點座標時發生錯誤: {e}",
                exc_info=True
            )
            return None
    
    # ===== 工具方法 =====
    
    def get_mapper(self, camera_id: str) -> Optional[BaseMapper]:
        """
        取得指定攝影機的座標映射器
        
        Args:
            camera_id: 攝影機 ID
            
        Returns:
            BaseMapper 實例或 None
        """
        return self.mappers.get(camera_id)
    
    def has_mapper(self, camera_id: str) -> bool:
        """
        檢查是否存在指定攝影機的座標映射器
        
        Args:
            camera_id: 攝影機 ID
            
        Returns:
            True 如果存在，False 否則
        """
        return camera_id in self.mappers
    
    def get_transform_mode(self) -> str:
        """
        取得當前的座標轉換模式
        
        Returns:
            'homography' 或 'tps'
        """
        return self.transform_mode
    
    def get_available_cameras(self) -> List[str]:
        """
        取得所有已初始化座標映射器的攝影機 ID 清單
        
        Returns:
            攝影機 ID 清單
        """
        return list(self.mappers.keys())
