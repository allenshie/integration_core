import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class ObjectData:
    camera_id: str
    class_name: str  # 物件類別（必須在有預設值的欄位之前）
    trajectory: list  # [(timestamp, x, y), ...]
    features: np.ndarray  # 特徵向量
    local_id: str = None  # 來自 MOT 的本地 ID
    global_id: str = None  # 全局 ID，初始為 None
    current_position: tuple = field(default_factory=tuple)
    update_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
