import numpy as np
import cv2
import os

from .base_mapper import BaseMapper

class HomographyMapper(BaseMapper):
    def __init__(self):
        self.H = None
        self.H_inv = None
        self.H_loaded = False

    def compute_and_save_homography(self, src_points, dst_points, file_path):
        """
        給定兩組對應點（Nx2 numpy array），計算 Homography 並儲存為 .npy 檔
        """
        if len(src_points) < 4 or len(dst_points) < 4:
            raise ValueError("至少需要4對對應點")
        
        src_pts = np.array(src_points, dtype=np.float32)
        dst_pts = np.array(dst_points, dtype=np.float32)
        
        H, status = cv2.findHomography(src_pts, dst_pts, method=0)
        
        if H is None:
            raise RuntimeError("找不到 Homography 矩陣，請檢查對應點是否合理")
        
        np.save(file_path, H)
        self.H = H
        self.H_inv = np.linalg.inv(H)
        self.H_loaded = True

    def load_homography(self, file_path):
        """
        從 .npy 檔載入 Homography 矩陣
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"檔案不存在: {file_path}")

        self.H = np.load(file_path)
        self.H_inv = np.linalg.inv(self.H)
        self.H_loaded = True
        return self
    
    def transform_point(self, point, inverse=False):
        """
        使用 Homography 對單點做轉換
        
        Args:
            point: 座標點 tuple (x, y)
            inverse: False=像素→全局座標, True=全局座標→像素
            
        Returns:
            轉換後的座標點 numpy array [x, y]
        """
        if not self.H_loaded:
            raise RuntimeError("尚未載入 Homography 矩陣，請先執行 load 或 compute")

        H = self.H_inv if inverse else self.H
        pt = np.array([point[0], point[1], 1.0])
        transformed = H @ pt
        transformed /= transformed[2]
        return tuple(transformed[:2])  # 返回 tuple 而非 numpy array

    def transform_points(self, points, inverse=False):
        """
        批次轉換點
        
        Args:
            points: 座標點陣列 Nx2 numpy array
            inverse: False=像素→全局座標, True=全局座標→像素
            
        Returns:
            轉換後的座標點陣列 Nx2 numpy array
        """
        if not self.H_loaded:
            raise RuntimeError("尚未載入 Homography 矩陣，請先執行 load 或 compute")

        H = self.H_inv if inverse else self.H
        pts = np.hstack([points, np.ones((points.shape[0], 1))])
        transformed = (H @ pts.T).T
        transformed /= transformed[:, [2]]
        return transformed[:, :2]


# if __name__=='__main__':
#     cam_name = 'camera2'    
#     save_path = f'{cam_name}_to_geo_map_homography_matrix.npy'
#     homography = Homography()
    
#     # 定義兩組對應點
#     cam_points = np.array([[700, 383], [2331, 440], [3359, 1612], [324, 1998]])
#     map_points = np.array([[210, 650], [258, 330], [1106, 660], [1121, 704]])
    
#     # 計算並儲存 Homography 矩陣
#     homography.compute_and_save_homography(cam_points, map_points, save_path)
    
#     # 載入 Homography 矩陣
#     homography.load_homography(save_path)
    
#     # 測試轉換
#     point = (700, 383)
#     transformed_point = homography.transform_point(point)
#     print(f"Transformed Point: {transformed_point}")