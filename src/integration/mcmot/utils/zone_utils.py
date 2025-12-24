import numpy as np
import cv2
from typing import List, Tuple, Optional, Dict


def polygon_to_npy(points: List[Tuple[int, int]], save_path: str) -> bool:
    """
    將多邊形點位轉換並保存為 .npy 檔案
    
    Args:
        points: 多邊形頂點列表 [(x1, y1), (x2, y2), ...]
        save_path: 保存檔案路徑
        
    Returns:
        bool: 保存是否成功
    """
    try:
        # 轉換為numpy陣列
        polygon_array = np.array(points, dtype=np.int32)
        
        # 保存為npy檔案
        np.save(save_path, polygon_array)
        
        print(f"Polygon saved to {save_path}")
        return True
        
    except Exception as e:
        print(f"Error saving polygon: {str(e)}")
        return False


def npy_to_polygon(npy_path: str, cache: Optional[Dict[str, Optional[np.ndarray]]] = None) -> Optional[np.ndarray]:
    """
    從 .npy 檔案載入多邊形數據
    
    Args:
        npy_path: .npy檔案路徑
        cache: 可選的緩存字典，如果提供則使用緩存機制
        
    Returns:
        Optional[np.ndarray]: 多邊形點位陣列，失敗時返回None
    """
    # 可選緩存檢查
    if cache is not None and npy_path in cache:
        return cache[npy_path]
    
    try:
        # 載入npy檔案
        polygon_array = np.load(npy_path)
        
        # 只在實際載入時顯示訊息
        print(f"Polygon loaded from {npy_path}")
        
        # 格式驗證和自動修正
        if polygon_array.ndim == 1:
            # 如果是一維數組，檢查是否可以重塑為二維
            if len(polygon_array) % 2 == 0:
                # 嘗試重塑為 (n, 2) 格式
                polygon_array = polygon_array.reshape(-1, 2)
                print(f"Auto-reshaped 1D array to shape {polygon_array.shape}")
                result = polygon_array
            else:
                print(f"Cannot reshape 1D array with odd length: {len(polygon_array)}")
                result = None
        elif polygon_array.ndim != 2 or polygon_array.shape[1] != 2:
            print(f"Invalid polygon shape: {polygon_array.shape}, expected (n, 2)")
            result = None
        else:
            result = polygon_array
        
        # 可選緩存儲存
        if cache is not None:
            cache[npy_path] = result
            
        return result
        
    except Exception as e:
        print(f"Error loading polygon: {str(e)}")
        result = None
        
        # 可選緩存失敗結果，避免重複嘗試
        if cache is not None:
            cache[npy_path] = result
            
        return result


def point_in_polygon(point: Tuple[int, int], polygon: np.ndarray) -> bool:
    """
    判斷點是否在多邊形內
    
    Args:
        point: 點位座標 (x, y)
        polygon: 多邊形點位陣列
        
    Returns:
        bool: 點是否在多邊形內
    """
    try:
        result = cv2.pointPolygonTest(polygon, point, False)
        return result >= 0  # >= 0 表示在多邊形內或邊界上
        
    except Exception as e:
        print(f"Error checking point in polygon: {str(e)}")
        return False


def get_bbox_bottom_center(bbox: List[float]) -> Tuple[int, int]:
    """
    取得bbox中間下方的點位
    
    Args:
        bbox: 邊界框 [x1, y1, x2, y2]
        
    Returns:
        Tuple[int, int]: 中間下方點位 (x, y)
    """
    x1, y1, x2, y2 = bbox
    center_x = int((x1 + x2) / 2)
    bottom_y = int(y2)
    return (center_x, bottom_y)


if __name__ == "__main__":
    # polygon_to_npy([
    #       [
    #         10.243902439024499,
    #         250.7317073170732
    #       ],
    #       [
    #         3434.6341463414633,
    #         292.1951219512195
    #       ],
    #       [
    #         3839,
    #         477
    #       ],
    #       [
    #         3839,
    #         2159
    #       ],
    #       [
    #         0.48780487804889106,
    #         2153.170731707317
    #       ]
    #     ], "camera4_VTS.npy")
    polygon = npy_to_polygon("camera2_EXT.npy")
    print(polygon)