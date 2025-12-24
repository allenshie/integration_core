from .loss_functions import LossFunctions
from .trajectory_utils import TrajectoryUtils
import numpy as np


# cost_matrix.py
class CostMatrix:

    @staticmethod
    def compute_cost_matrix(local_objects, global_objects, current_timestamp, backtrack_seconds, traj_method="dtw", alpha=0.5, max_traj_loss=100.0):
        N, M = len(local_objects), len(global_objects)
        traj_losses = np.zeros((N, M))
        feature_losses = np.zeros((N, M))

        for i in range(N):
            for j in range(M):
                traj1 = TrajectoryUtils.interpolate_trajectory(local_objects[i].trajectory, current_timestamp, backtrack_seconds)
                traj2 = TrajectoryUtils.interpolate_trajectory(global_objects[j].trajectory, current_timestamp, backtrack_seconds)
                traj_losses[i, j] = LossFunctions.compute_trajectory_difference(traj1, traj2, method=traj_method)

                if local_objects[i].features is None or global_objects[j].features is None:
                    feature_losses[i, j] = 0.0
                else:
                    feature_losses[i, j] = LossFunctions.compute_feature_difference(local_objects[i].features, global_objects[j].features)

        # Normalize traj_loss using fixed upper bound
        traj_losses = traj_losses / max_traj_loss
        traj_losses = np.clip(traj_losses, 0, 1)
        
        cost_matrix = traj_losses + alpha * feature_losses
        CostMatrix.print_cost_matrix(cost_matrix, mock_column=False)
        return cost_matrix


    @staticmethod
    def print_cost_matrix(cost_matrix, mock_column=True):
        rows, cols = cost_matrix.shape

        # 標題列處理
        header = "      |"
        for j in range(cols):
            if mock_column and j == cols - 1:
                header += f" {'u_mock':<7}"
            else:
                header += f" u_{j:<6}"
        print(header)
        print("-" * len(header))

        # 資料列處理
        for i in range(rows):
            row_str = f"t_{i:<4}|"
            for j in range(cols):
                row_str += f" {cost_matrix[i, j]:<7.2f}"
            print(row_str)
