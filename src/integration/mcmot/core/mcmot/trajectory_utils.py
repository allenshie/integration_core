from datetime import datetime, timedelta
import numpy as np
from pykalman import KalmanFilter

class TrajectoryUtils:
    @staticmethod
    def initialize_kalman_filter(dt=1.0):
        transition_matrix = np.array([[1, dt, 0,  0],
                                     [0,  1, 0,  0],
                                     [0,  0, 1, dt],
                                     [0,  0, 0,  1]])
        observation_matrix = np.array([[1, 0, 0, 0],
                                      [0, 0, 1, 0]])
        initial_state_mean = np.array([0.0, 0.0, 0.0, 0.0])
        initial_state_covariance = np.eye(4) * 1000
        process_noise = np.eye(4) * 0.01
        observation_noise = np.eye(2) * 0.1

        return KalmanFilter(
            transition_matrices=transition_matrix,
            observation_matrices=observation_matrix,
            initial_state_mean=initial_state_mean,
            initial_state_covariance=initial_state_covariance,
            transition_covariance=process_noise,
            observation_covariance=observation_noise
        )

    @staticmethod
    def interpolate_second_segment_linear(traj_sorted, start_time, end_time, time_step=1.0):
        """用線性插值補齊第二類數據"""
        time_slots = [start_time + timedelta(seconds=i * time_step) 
                      for i in range(int((end_time - start_time).total_seconds() / time_step) + 1)]
        second_traj = [(slot, None, None) for slot in time_slots]

        for i, (t, _, _) in enumerate(second_traj):
            prev_points = [(ts, x, y) for ts, x, y in traj_sorted if ts <= t]
            next_points = [(ts, x, y) for ts, x, y in traj_sorted if ts > t]
            
            if prev_points and next_points:
                prev_t, prev_x, prev_y = prev_points[-1]
                next_t, next_x, next_y = next_points[0]
                if t == prev_t:
                    second_traj[i] = (t, prev_x, prev_y)
                else:
                    time_diff = (next_t - prev_t).total_seconds()
                    slot_diff = (t - prev_t).total_seconds()
                    weight = slot_diff / time_diff if time_diff > 0 else 0
                    interp_x = prev_x + (next_x - prev_x) * weight
                    interp_y = prev_y + (next_y - prev_y) * weight
                    second_traj[i] = (t, interp_x, interp_y)
            elif prev_points:
                second_traj[i] = (t, prev_points[-1][1], prev_points[-1][2])
                
        # 過濾出有效點
        valid_traj = [p for p in second_traj if p[1] is not None and p[2] is not None]

        # 補足不足兩筆的情況
        if len(valid_traj) == 1:
            # 複製一筆稍微往後挪的時間點，或其他處理策略
            t, x, y = valid_traj[0]
            second_traj.append((t + timedelta(seconds=time_step), x, y))

        return [p for p in second_traj if p[1] is not None and p[2] is not None]

    @staticmethod
    def interpolate_first_segment(start_time, first_obs_time, second_traj, time_step=1.0):
        """用卡爾曼濾波從第二類數據向前推斷第一類數據"""
        time_slots = [start_time + timedelta(seconds=i * time_step) 
                      for i in range(int((first_obs_time - start_time).total_seconds() / time_step))]
        first_traj = [(slot, None, None) for slot in time_slots]

        if not second_traj:
            return [(t, 0.0, 0.0) for t, _, _ in first_traj]

        kf = TrajectoryUtils.initialize_kalman_filter(dt=time_step)
        
        obs = np.array([[x, y] for _, x, y in second_traj])
        state_means, state_covariances = kf.filter(obs)

        if len(second_traj) >= 2:
            t1, x1, y1 = second_traj[0]
            t2, x2, y2 = second_traj[1]
            dt = (t2 - t1).total_seconds()
            vx = (x2 - x1) / dt if dt > 0 else 0.0
            vy = (y2 - y1) / dt if dt > 0 else 0.0
            initial_state_mean = np.array([x1, vx, y1, vy])
        else:
            initial_state_mean = np.array([second_traj[0][1], 0.0, second_traj[0][2], 0.0])

        first_traj.reverse()
        current_state_mean = initial_state_mean
        current_state_cov = state_covariances[0] if len(state_covariances) > 0 else np.eye(4) * 0.01

        for i, (t, _, _) in enumerate(first_traj):
            current_state_mean = np.linalg.inv(kf.transition_matrices) @ current_state_mean
            current_state_cov = (np.linalg.inv(kf.transition_matrices) @ current_state_cov @ 
                               np.linalg.inv(kf.transition_matrices).T + kf.transition_covariance)
            first_traj[i] = (t, current_state_mean[0], current_state_mean[2])
        first_traj.reverse()

        return first_traj

    @staticmethod
    def interpolate_third_segment(last_obs_time, end_time, second_traj, time_step=1.0):
        """用卡爾曼濾波從第二類數據向後推斷第三類數據"""
        time_slots = [last_obs_time + timedelta(seconds=(i + 1) * time_step) 
                      for i in range(int((end_time - last_obs_time).total_seconds() / time_step))]
        third_traj = [(slot, None, None) for slot in time_slots]

        if not second_traj:
            return [(t, 0.0, 0.0) for t, _, _ in third_traj]

        kf = TrajectoryUtils.initialize_kalman_filter(dt=time_step)
        obs = np.array([[x, y] for _, x, y in second_traj])
        state_means, state_covariances = kf.filter(obs)

        if len(second_traj) >= 2:
            t1, x1, y1 = second_traj[-2]
            t2, x2, y2 = second_traj[-1]
            dt = (t2 - t1).total_seconds()
            vx = (x2 - x1) / dt if dt > 0 else 0.0
            vy = (y2 - y1) / dt if dt > 0 else 0.0
            initial_state_mean = np.array([x2, vx, y2, vy])
        else:
            initial_state_mean = np.array([second_traj[-1][1], 0.0, second_traj[-1][2], 0.0])

        current_state_mean = initial_state_mean
        current_state_cov = state_covariances[-1] if len(state_covariances) > 0 else np.eye(4) * 0.01

        for i, (t, _, _) in enumerate(third_traj):
            current_state_mean = kf.transition_matrices @ current_state_mean
            current_state_cov = (kf.transition_matrices @ current_state_cov @ 
                               kf.transition_matrices.T + kf.transition_covariance)
            third_traj[i] = (t, current_state_mean[0], current_state_mean[2])

        return third_traj

    @staticmethod
    def interpolate_trajectory(traj, current_time, backtrack_time, time_step=1.0):
        """
        整合函數：根據軌跡、當前時間和回溯時間補齊所有缺失值
        :param traj: 觀測軌跡 [(timestamp, x, y), ...]
        :param current_time: 當前時間（datetime）
        :param backtrack_time: 回溯時間（秒）
        :param time_step: 時間間隔（秒）
        :return: 補齊後的完整軌跡 [(timestamp, x, y), ...]
        """
        # if not traj:
        #     start_time = current_time - timedelta(seconds=backtrack_time)
        #     end_time = current_time
        #     time_slots = [start_time + timedelta(seconds=i * time_step) 
        #                   for i in range(int((end_time - start_time).total_seconds() / time_step) + 1)]
        #     return [(t, 0.0, 0.0) for t in time_slots]

        traj_sorted = sorted(traj, key=lambda x: x[0])
        first_obs_time = traj_sorted[0][0]
        last_obs_time = traj_sorted[-1][0]
        start_time = current_time - timedelta(seconds=backtrack_time)
        end_time = current_time  # 假設 current_time 是軌跡的結束時間

        # 步驟1：補齊第二類數據
        second_traj = TrajectoryUtils.interpolate_second_segment_linear(traj_sorted, first_obs_time, last_obs_time, time_step)

        # 步驟2：推斷第一類數據
        first_traj = TrajectoryUtils.interpolate_first_segment(start_time, first_obs_time, second_traj, time_step)

        # 步驟3：推斷第三類數據
        third_traj = TrajectoryUtils.interpolate_third_segment(last_obs_time, end_time, second_traj, time_step)

        # 整合結果
        all_traj = first_traj + second_traj + third_traj

        return TrajectoryUtils.filter_by_slot(current_time, backtrack_time, time_step, all_traj)  # 使用filter_by_slot
    
    @staticmethod
    def filter_by_slot(current_time, backtrack_time, time_step, traj):
        """
        將traj按時間切成slot，每個slot只保留一個最早的點
        :param current_time: datetime，當前時間
        :param backtrack_time: float，回溯時間（秒）
        :param time_step: float，slot 的時間間隔（秒）
        :param traj: List[(timestamp, x, y)]
        :return: List[(timestamp, x, y)]，每個slot只保留一筆資料
        """
        start_time = current_time - timedelta(seconds=backtrack_time)
        end_time = current_time
        num_slots = int((end_time - start_time).total_seconds() / time_step)

        # 建立時間 slot 邊界
        time_slots = [start_time + timedelta(seconds=i * time_step) for i in range(num_slots + 1)]

        # 為每個slot找到第一筆符合條件的點
        final_traj = []
        for i in range(len(time_slots) - 1):
            slot_start = time_slots[i]
            slot_end = time_slots[i + 1]

            # 找到落在這個slot中的資料點
            points_in_slot = [p for p in traj if slot_start <= p[0] < slot_end]

            if points_in_slot:
                # 只取slot中的第一個點（按時間最早）
                points_in_slot.sort(key=lambda p: p[0])
                _, x, y = points_in_slot[0]
                final_traj.append(((slot_start.replace(microsecond=0)), x, y))
                
        return final_traj

    
    @staticmethod
    def merge_trajectories(global_traj, local_traj):
        """
        合併全局軌跡與局部軌跡
        """
        global_dict = {t: (x, y) for t, x, y in global_traj}
        local_dict = {t: (x, y) for t, x, y in local_traj}
        
        all_timestamps = sorted(set(global_dict.keys()) | set(local_dict.keys()))
        
        merged_traj = []
        for t in all_timestamps:
            if t in global_dict and t not in local_dict:
                merged_traj.append((t, global_dict[t][0], global_dict[t][1]))
            elif t in local_dict and t not in global_dict:
                merged_traj.append((t, local_dict[t][0], local_dict[t][1]))
            elif t in global_dict and t in local_dict:
                avg_x = (global_dict[t][0] + local_dict[t][0]) / 2
                avg_y = (global_dict[t][1] + local_dict[t][1]) / 2
                merged_traj.append((t, avg_x, avg_y))
        
        return merged_traj
    
    @staticmethod
    def update_global_trajectory(
        global_trajectory: list[tuple[str, float, float]],
        local_trajectories: dict[str, list[tuple[str, float, float]]],
        default_weight: float = 1.0
    ) -> list[tuple[str, float, float]]:
        """
        將所有局部軌跡在 [全局最新時間戳, 當前] 這段時間內進行時間對齊與加權平均，
        然後合併更新到全局軌跡中。

        :param global_trajectory: List of (t, x, y)，全局軌跡資料
        :param local_trajectories: Dict[camera_id -> List[(t, x, y)]]
        :param default_weight: 每支攝影機的預設權重
        :return: 更新後的全局軌跡 List[(t, x, y)]
        """
        from collections import defaultdict

        # 轉為 dict 方便更新
        global_dict = {t: (x, y) for t, x, y in global_trajectory}
        latest_global_time = max(global_dict.keys()) if global_dict else ""

        # 蒐集新區段的所有時間戳對應點
        points_by_time = defaultdict(list)
        for cam_id, traj in local_trajectories.items():
            for t, x, y in traj:
                if t > latest_global_time:
                    points_by_time[t].append((x, y, default_weight))

        # 對每個時間戳進行加權平均
        for t in sorted(points_by_time.keys()):
            points = points_by_time[t]
            total_weight = sum(w for _, _, w in points)
            avg_x = sum(x * w for x, _, w in points) / total_weight
            avg_y = sum(y * w for _, y, w in points) / total_weight
            global_dict[t] = (avg_x, avg_y)

        # 回傳更新後軌跡（時間排序）
        updated_traj = sorted([(t, x, y) for t, (x, y) in global_dict.items()])
        return updated_traj
    
    
# 測試範例
if __name__ == "__main__":
    current_time = datetime(2025, 3, 25, 12, 0, 32)  # 假設當前時間為 12:00:32
    backtrack_time = 10  # 回溯 20 秒
    traj = [
        (current_time - timedelta(seconds=17), 2.0, 3.0),  # 15s
        (current_time - timedelta(seconds=13), 4.0, 5.0),  # 19s
        (current_time - timedelta(seconds=10), 6.0, 7.0),  # 22s
        (current_time - timedelta(seconds=5), 9.0, 10.0),  # 27s
    ]

    # 補齊軌跡
    result = TrajectoryUtils.interpolate_trajectory(traj, current_time, backtrack_time, time_step=1.0)
    print("補齊後的完整軌跡：")
    print(len(result))
    for t, x, y in result:
        print(f"Time: {t.strftime('%S')}, Position: ({x:.2f}, {y:.2f})")