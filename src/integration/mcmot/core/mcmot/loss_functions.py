import numpy as np
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean
import torch.nn.functional as F

class LossFunctions:
    @staticmethod
    def compute_trajectory_difference(traj1, traj2, method="dtw"):
        """
        計算兩條歷史軌跡的差異，使用 DTW 或歐幾里得距離。
        針對不同起始時間的軌跡進行對齊，確保時間同步。

        :param traj1: [(timestamp, x, y), ...] 軌跡 1
        :param traj2: [(timestamp, x, y), ...] 軌跡 2
        :param method: "euclidean" 或 "dtw"
        :return: Loss 值
        """
        # 取得對齊的時間範圍

        # 取得時間戳與坐標

        timestamps1, xs1, ys1 = zip(*traj1)
        timestamps2, xs2, ys2 = zip(*traj2)

        # 合併 x, y 坐標
        coords1 = list(zip(xs1, ys1))
        coords2 = list(zip(xs2, ys2))

        # 找到兩軌跡共同的時間戳
        common_timestamps = sorted(set(timestamps1) & set(timestamps2))
        if len(common_timestamps) == 0:
            return float('inf')

        # 過濾出共同時間戳的座標
        coords1_filtered = np.array([p for t, p in zip(timestamps1, coords1) if t in common_timestamps])
        coords2_filtered = np.array([p for t, p in zip(timestamps2, coords2) if t in common_timestamps])

        if method == "euclidean":
            return np.sum((coords1_filtered - coords2_filtered) ** 2)
        elif method == "dtw":
            distance, _ = fastdtw(coords1_filtered, coords2_filtered, dist=euclidean)
            return distance

        return float('inf')

    @staticmethod
    def compute_feature_difference(feature1, feature2):
        return 1 - F.cosine_similarity(feature1, feature2)