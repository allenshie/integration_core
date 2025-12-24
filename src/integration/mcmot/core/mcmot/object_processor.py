from typing import List, Dict, Optional
from datetime import datetime, timezone
from integration.mcmot.utils.logger import get_logger

from integration.mcmot.core.mcmot.record_service import RecordService


class ObjectProcessor:
    """
    處理檢測到的物體，進行後續的處理和轉換
    不再負責物體檢測，專注於物體資料的處理
    """
    
    def __init__(self, config):
        """
        Initialize object processor
        
        Args:
            config: 配置物件
        """
        self.logger = get_logger(
            name="object_processor",
            log_file="mcmot_coordinator"
        )
        self.config = config
        self.record_service = RecordService()
    
    def process_objects_for_tracking(self, objects: List[Dict], camera_id: str, 
                                   timestamp: datetime) -> List[Dict]:
        """
        處理物體進行追蹤準備
        
        Args:
            objects: 檢測到的物體列表
            camera_id: 攝影機ID
            timestamp: 時間戳記
            
        Returns:
            處理後的物體列表
        """
        try:
            if len(objects) == 0:
                return []
            
            # 為物體添加時間戳記和攝影機資訊
            processed_objects = []
            for obj in objects:
                processed_obj = obj.copy()
                processed_obj.update({
                    'camera_id': camera_id,
                    'timestamp': timestamp,
                    'processed_at': datetime.now(timezone.utc)
                })
                processed_objects.append(processed_obj)
            
            # 記錄處理結果
            self.record_service.record_objects(
                camera_id=camera_id,
                objects=processed_objects,
                timestamp=timestamp
            )
            
            self.logger.debug(f"Processed {len(processed_objects)} objects from {camera_id}")
            return processed_objects
            
        except Exception as e:
            self.logger.error(f"Error processing objects from {camera_id}: {e}")
            return []
    
    def update_global_ids(self, objects: List[Dict], id_mapping: Optional[Dict[int, int]]) -> None:
        """
        Update objects with global IDs based on mapping
        
        Args:
            objects: List of objects to update
            id_mapping: Mapping from local ID to global ID
        """
        if id_mapping is None:
            return
        
        for obj in objects:
            local_id = obj.get('local_id')
            if local_id is not None:
                global_id = id_mapping.get(local_id)
                obj['global_id'] = global_id
        
        self.logger.debug(f"Updated global IDs for {len(objects)} objects")
    
    def validate_objects(self, objects: List[Dict]) -> List[Dict]:
        """
        Validate detected objects and filter out invalid ones
        
        Args:
            objects: List of objects to validate
            
        Returns:
            List of valid objects
        """
        valid_objects = []
        
        for obj in objects:
            if self._is_valid_object(obj):
                valid_objects.append(obj)
            else:
                self.logger.debug(f"Filtered out invalid object: {obj.get('local_id', 'unknown')}")
        
        return valid_objects
    
    def _is_valid_object(self, obj: Dict) -> bool:
        """
        Check if an object is valid
        
        Args:
            obj: Object to validate
            
        Returns:
            True if object is valid, False otherwise
        """
        # Check required fields
        required_fields = ['bbox', 'local_id']
        for field in required_fields:
            if field not in obj:
                return False
        
        # Validate bounding box
        bbox = obj['bbox']
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            return False
        
        # Check bbox coordinates are reasonable
        x1, y1, x2, y2 = bbox
        if x2 <= x1 or y2 <= y1:
            return False
        
        # Check bbox size is reasonable (not too small)
        width = x2 - x1
        height = y2 - y1
        min_size = 10  # Minimum object size in pixels
        
        if width < min_size or height < min_size:
            return False
        
        return True
    
    def get_object_statistics(self) -> Dict[str, int]:
        """
        Get statistics about processed objects
        
        Returns:
            Dictionary containing statistics
        """
        # This could be expanded to track more detailed statistics
        return {
            'total_processed': getattr(self, '_total_processed', 0),
            'total_valid': getattr(self, '_total_valid', 0),
            'total_invalid': getattr(self, '_total_invalid', 0),
        }
    
    def reset_statistics(self) -> None:
        """Reset object processing statistics"""
        self._total_processed = 0
        self._total_valid = 0
        self._total_invalid = 0
