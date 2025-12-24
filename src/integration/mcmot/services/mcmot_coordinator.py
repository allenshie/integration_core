"""
MCMOT Coordinator
Main coordinator class that orchestrates all components of the MC-MOT system
"""

import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timezone
from integration.mcmot.utils.logger import get_logger

from integration.mcmot.core.mcmot.object_processor import ObjectProcessor
from integration.mcmot.core.coordinate.coordinate_transformer import CoordinateTransformer
from integration.mcmot.core.mcmot.trajectory_analyzer import TrajectoryAnalyzer
from integration.mcmot.core.mcmot.gallery import Gallery
from integration.mcmot.utils.zone_utils import npy_to_polygon


class MCMOTCoordinator:
    """
    Main coordinator for Multi-Camera Multi-Object Tracking system
    
    這個類別完全解耦，不依賴任何外部配置載入邏輯
    專注於多攝影機追蹤、座標轉換和軌跡分析
    配置由外部（core）統一管理並傳入
    """
    
    def __init__(self, config, zone_service=None):
        """
        Initialize MCMOT Coordinator
        
        Args:
            config: 配置物件（虛擬方式，不指定類型以減少依賴）
        """
        self.logger = get_logger(
            name="mcmot_coordinator",
            log_file="mcmot_coordinator"
        )
        
        # 直接使用外部傳入的配置物件
        if not config:
            raise ValueError("Configuration is required")
        
        self.config = config
        
        # 載入可追蹤類別配置
        self.trackable_classes = config.tracking.trackable_classes
        self.logger.info(f"可追蹤類別: {self.trackable_classes}")
        
        # 使用共享的區域服務或創建專用快取
        if zone_service is not None:
            self.zone_service = zone_service
            self.logger.info("從ZoneService獲取區域資訊")
        else:
            self.zone_service = None
            self.logger.warning("未提供共享區域服務，將使用獨立快取")
        
        # 添加相機配置緩存，避免重複載入 .npy 檔案
        self._camera_config_cache = {}
        self._polygon_cache = {}  # 專用的多邊形緩存（向後兼容）
        
        self._initialize_components()
        self._preload_camera_configs()  # 預載入所有相機配置
        self.logger.info("MCMOT Coordinator initialized successfully")
    
    def _initialize_components(self) -> None:
        """Initialize all system components"""
        try:
            # 初始化追蹤相關組件，配置都從外部傳入
            self.object_processor = ObjectProcessor(self.config)
            self.coordinate_transformer = CoordinateTransformer(self.config)
            self.trajectory_analyzer = TrajectoryAnalyzer(self.config)
            
            # Initialize gallery for global tracking
            map_scale = self._build_map_scale()
            tracking_cfg = getattr(self.config, "tracking", None)
            distance_threshold = tracking_cfg.distance_threshold_m if tracking_cfg else None
            match_threshold = tracking_cfg.match_threshold if tracking_cfg else None
            max_traj_loss = tracking_cfg.max_traj_loss if tracking_cfg else None
            self.gallery = Gallery(
                map_scale=map_scale,
                distance_threshold_m=distance_threshold,
                match_threshold=match_threshold,
                max_traj_loss=max_traj_loss,
            )
            
            self.logger.info("All MCMOT components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise
    
    def _preload_camera_configs(self):
        """預載入所有相機配置，避免運行時重複載入 .npy 檔案"""
        try:
            enabled_cameras = self.config.get_enabled_camera()
            self.logger.info(f"Preloading configurations for {len(enabled_cameras)} cameras...")
            
            for camera in enabled_cameras:
                edge_key = camera.edge_id or camera.camera_id
                camera_config = {
                    'enabled': camera.enabled,
                    'camera_id': camera.camera_id,
                    'name': camera.name,
                    'edge_id': edge_key,
                    'coordinate_matrix_ckpt': camera.coordinate_matrix_ckpt,
                }
                
                # 使用共享區域服務或獨立載入
                if self.zone_service is not None:

                    camera_config['ignore_polygons'] = npy_to_polygon(camera.ignore_polygons, self._polygon_cache) if camera.ignore_polygons else None
                else:
                    # 向後兼容：使用獨立快取
                    camera_config['ignore_polygons'] = npy_to_polygon(camera.ignore_polygons, self._polygon_cache) if camera.ignore_polygons else None
                
                self._camera_config_cache[edge_key] = camera_config
                if edge_key != camera.camera_id:
                    self._camera_config_cache[camera.camera_id] = camera_config
                self.logger.debug(f"Preloaded config for camera {edge_key} -> {camera.camera_id}")
                
        except Exception as e:
            self.logger.error(f"Error preloading camera configs: {e}")
            
    def _get_camera_config(self, edge_camera_id: str) -> Optional[Dict]:
        """獲取指定相機的配置（使用緩存）"""
        return self._camera_config_cache.get(edge_camera_id)
    
    def _filter_trackable_objects(self, objects: List[Dict]) -> List[Dict]:
        """
        過濾出可追蹤的物件類別
        
        Args:
            objects: 檢測到的物件列表
            
        Returns:
            只包含可追蹤類別的物件列表
        """
        trackable = [
            obj for obj in objects 
            if obj.get('class_name') in self.trackable_classes
        ]
        
        filtered_count = len(objects) - len(trackable)
        if filtered_count > 0:
            self.logger.debug(
                f"過濾掉 {filtered_count} 個不可追蹤的物件 "
                f"(保留 {len(trackable)} 個可追蹤物件)"
            )
        
        return trackable
    
    def process_detected_objects(self, detected_objects: List[Dict], camera_id: str,
                                timestamp: Optional[datetime] = None, 
                                image: Optional[np.ndarray] = None) -> List[Dict]:
        """
        處理外部檢測結果進行全域追蹤
        
        這是 MCMOTCoordinator 的主要對外介面，接受外部檢測結果
        
        Args:
            detected_objects: 外部檢測服務返回的物體列表
            camera_id: 攝影機ID
            timestamp: 時間戳記
            image: 原始圖像（可選，某些座標轉換可能需要圖像尺寸資訊）
            
        Returns:
            處理後的物體列表，包含全域追蹤資訊
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        # Validate camera configuration
        camera_config = self._get_camera_config(camera_id)
        if camera_config is None or not camera_config.get('enabled', False):
            self.logger.warning(f"Camera %s is not configured or disabled", camera_id)
            return []
        config_camera_id = camera_config.get('camera_id', camera_id)
        
        try:
            # Step 1: 過濾可追蹤類別
            trackable_objects = self._filter_trackable_objects(detected_objects)
            
            if len(trackable_objects) == 0:
                self.logger.debug(f"No trackable objects from {camera_id}")
                return []
            
            # Step 2: 使用 ObjectProcessor 建立軌跡記錄
            processed_objects = self.object_processor.process_objects_for_tracking(
                objects=trackable_objects,
                camera_id=config_camera_id,
                timestamp=timestamp
            )
            
            # Step 3: 進行全域追蹤處理
            global_tracking_objects = self._process_for_global_tracking(
                objects=processed_objects,
                camera_id=config_camera_id,
                camera_config=camera_config,
                timestamp=timestamp
            )
                
            # Step 4: 更新全域ID映射
            id_mapping = self.gallery.local_global_mapping.get(config_camera_id)
            self.object_processor.update_global_ids(global_tracking_objects, id_mapping)
            
            self.logger.debug(f"Processed {len(global_tracking_objects)} objects from {camera_id} -> {config_camera_id}")
            return global_tracking_objects
            
        except Exception as e:
            self.logger.error(f"Error processing detected objects from {camera_id}: {e}")
            return []
    
    def _process_for_global_tracking(self, objects: List[Dict], camera_id: str,
                                   camera_config: Dict, timestamp: datetime) -> List[Dict]:
        """
        Process objects for global tracking
        
        Args:
            objects: Detected objects
            camera_id: ID of the camera
            camera_config: Camera configuration dictionary
            timestamp: Current timestamp
            
        Returns:
            List of processed objects ready for global tracking
        """
        # Step 1: Transform coordinates to global system
        transform_success = self.coordinate_transformer.transform_local_to_global(
            camera_id=camera_id,
            objects=objects
        )
        
        if not transform_success:
            self.logger.warning(f"Coordinate transformation failed for {camera_id}")
            return objects

        # 🔍 除錯：檢查座標轉換結果
        # objects_with_global_traj = [obj for obj in objects if obj.get('global_trajectory')]
        # objects_without_global_traj = [obj for obj in objects if not obj.get('global_trajectory')]

        # self.logger.info(f"[座標轉換後] {camera_id}: "
        #                 f"有 global_trajectory: {len(objects_with_global_traj)}, "
        #                 f"沒有: {len(objects_without_global_traj)}")

        # if objects_without_global_traj:
        #     missing_ids = [obj.get('local_id') for obj in objects_without_global_traj]
        #     self.logger.warning(f"[座標轉換] 以下物件沒有 global_trajectory: {missing_ids}")

        # Step 2: Filter objects outside ignore areas
        ignore_polygons = camera_config.get('ignore_polygons', None)
        # 將單個多邊形轉換為多邊形列表（最小變動）
        ignore_areas = []
        if ignore_polygons is not None:
            ignore_areas = [ignore_polygons]

        filtered_objects = self.trajectory_analyzer.filter_objects_by_ignore_areas(
            objects=objects,
            ignore_areas=ignore_areas
        )

        # # 🔍 添加調試
        # self.logger.info(f"[過濾前] {len(objects)} 個物件，[過濾後] {len(filtered_objects)} 個物件")
        # if len(filtered_objects) < len(objects):
        #     filtered_ids = [obj.get('local_id') for obj in filtered_objects]
        #     all_ids = [obj.get('local_id') for obj in objects]
        #     removed = set(all_ids) - set(filtered_ids)
        #     self.logger.warning(f"[過濾] 被移除的物件: {removed}")

        # Step 4: Update global gallery
        # self.logger.info(f"[傳入 Gallery] {camera_id}: {len(filtered_objects)} 個物件, "
        #                 f"local_ids = {[obj.get('local_id') for obj in filtered_objects]}")

        tracking_cfg = getattr(self.config, "tracking", None)
        threshold = tracking_cfg.match_threshold if tracking_cfg else None
        max_traj_loss = tracking_cfg.max_traj_loss if tracking_cfg else None

        self.gallery.batch_update_or_register(
            camera_id=camera_id,
            local_objects=filtered_objects,
            current_timestamp=timestamp,
            threshold=threshold,
            max_traj_loss=max_traj_loss,
        )
        self.logger.debug(f"[Gallery 更新後] 全域物件總數: {len(self.gallery.global_objects)}")
        
        return objects  # Return original objects with global info added
    
    def finalize_global_updates(self, timestamp: Optional[datetime] = None) -> None:
        """
        Finalize pending global updates
        
        Args:
            timestamp: Current timestamp (uses current time if None)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        try:
            self.gallery.apply_pending_updates(timestamp)
            self.logger.debug("Global updates finalized")
            
        except Exception as e:
            self.logger.error(f"Error finalizing global updates: {e}")
    
    def get_all_global_objects(self) -> List[Dict]:
        """
        Get all objects in the global tracking system
        
        Returns:
            List of all global objects
        """
        try:
            return list(self.gallery.global_objects.values())
        except Exception as e:
            self.logger.error(f"Error getting global objects: {e}")
            return []
    
    def reload_configuration(self, config_name: str = 'config') -> bool:
        """
        Reload system configuration
        
        Args:
            config_name: Name of configuration to reload
            
        Returns:
            True if reload successful, False otherwise
        """
        try:
            # 重新載入配置
            new_config = self.config_handler.reload_config(config_name)
            
            # 簡單驗證：確保必要的鍵存在
            required_keys = ['cameras', 'system', 'tracking']
            missing_keys = [key for key in required_keys if key not in new_config]
            
            if missing_keys:
                self.logger.error(f"Configuration missing required keys: {missing_keys}")
                return False
            
            # 更新配置
            self.config = new_config
            
            # 重新初始化依賴配置的組件
            self.coordinate_transformer = CoordinateTransformer(self.config)
            self.trajectory_analyzer = TrajectoryAnalyzer(self.config)
            
            self.logger.info(f"Configuration '{config_name}' reloaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error reloading configuration '{config_name}': {e}")
            return False
    
    def cleanup(self) -> None:
        """Cleanup resources and finalize operations"""
        try:
            # Finalize any pending operations
            self.finalize_global_updates()
            
            # Additional cleanup if needed
            self.logger.info("MCMOT Coordinator cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def _build_map_scale(self) -> Optional[Dict[str, float]]:
        map_cfg = getattr(self.config, "map", None)
        if not map_cfg:
            return None
        try:
            return {
                "meters_per_pixel_x": map_cfg.meters_per_pixel_x,
                "meters_per_pixel_y": map_cfg.meters_per_pixel_y,
            }
        except Exception as exc:
            self.logger.error(f"無法建立地圖比例資訊: {exc}")
            return None
