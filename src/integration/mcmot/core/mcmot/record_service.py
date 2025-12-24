from integration.mcmot.core.mcmot.expiring_dict import ExpiringDict

from collections import deque
from datetime import datetime, timezone


class RecordService:
    def __init__(self):
        """
        初始化記錄服務
        """
        # 使用 ExpiringDict 來存儲過期的物件
        self.record_table = ExpiringDict(expiration_seconds=60)

    def record_trajectory(self, timestamp: datetime, camera_id: str, objects: list):
        # 清除過期的物件
        self.cleanup_all()

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        
        # 檢查攝影機 ID 是否存在於記錄表中
        if camera_id not in self.record_table:
            self.record_table[camera_id] = ExpiringDict(expiration_seconds=60)

        record_table = self.record_table[camera_id]
        
        # 更新物件的軌跡
        for obj in objects:
            track_id = obj.get('local_id')
            if track_id is None:
                continue  # 跳過沒有 track_id 的物件
            
            x1, y1, x2, y2 = obj['bbox']
            # 保持 datetime 格式，讓 TrajectoryUtils 可以正常處理
            current_trajectory = [timestamp, (x2+x1)//2, y2]
            
            if track_id not in record_table:
                record_table[track_id] = {'trajectory':deque(maxlen=30),
                                          }  # 限制歷史記錄最大長度
                
            trajectory_deque = record_table[track_id]['trajectory']
            trajectory_deque.append(current_trajectory)
            
            obj.update({
                'camera_id': camera_id, 
                'local_trajectory': list(trajectory_deque)})  # 修正 JSON 不可序列化 deque

    def record_objects(self, camera_id: str, objects: list, timestamp: datetime):
        """
        記錄物件並建立軌跡 - 與 record_trajectory 相同功能，統一接口
        
        Args:
            camera_id: 攝影機ID
            objects: 物件列表
            timestamp: 時間戳記
        """
        self.record_trajectory(timestamp, camera_id, objects)
    
    def cleanup_all(self):
        # 可選的全域清理函式（例如定時呼叫）
        for _, camera_dict in self.record_table.get_store().items():
            camera_dict.cleanup()
