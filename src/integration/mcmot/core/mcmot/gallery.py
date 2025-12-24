from .models import ObjectData
from .trajectory_matcher import TrajectoryMatcher
from .trajectory_utils import TrajectoryUtils
from integration.mcmot.utils.logger import get_logger

import math
import torch
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from collections import defaultdict


class Gallery:
    def __init__(
        self,
        backtrack_seconds=5,
        confirmation_frames=5,
        map_scale: Optional[Dict[str, float]] = None,
        distance_threshold_m: Optional[float] = None,
        match_threshold: Optional[float] = None,
        max_traj_loss: Optional[float] = None,
    ):
        """初始化全局軌跡儲存"""
        self.logger = get_logger(name="gallery", log_file="mcmot_coordinator")

        self.matcher = TrajectoryMatcher(
            max_traj_loss=max_traj_loss,
            match_threshold=match_threshold,
        )
        self.backtrack_seconds = backtrack_seconds
        self.confirmation_frames = confirmation_frames  # 需要連續確認的幀數
        self.global_objects = dict()  # {global_id: ObjectData}
        self.next_global_id = 0
        self.local_global_mapping = dict() # {cam: {local_id: global_id}}
        self.pending_updates: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"trajectories": [], "features": []})

        # 候選池：{camera_id: {local_id: {"hits": int, "data": ObjectData, "first_seen": datetime, "last_seen": datetime}}}
        self.candidate_objects: Dict[str, Dict[int, Dict[str, Any]]] = defaultdict(dict)
        self.map_scale = map_scale
        self.distance_threshold_m = distance_threshold_m
        self._distance_warning_logged = False
        if self.distance_threshold_m is not None and self.map_scale is None:
            self.logger.warning("已啟用距離閾值但缺少地圖比例設定，將跳過距離檢查")

    def trans_to_ObjectData(self, camera_id, objects):
        new_objects = []
        for obj in objects:
            new_objects.append(ObjectData(
                camera_id=camera_id,
                class_name=obj.get('class_name', ''),
                trajectory=obj.get('global_trajectory', []),
                features=obj.get('feature', None),
                local_id=obj['local_id'],
                global_id=obj['global_id']
            ))
        return new_objects


    def batch_update_or_register(
        self,
        camera_id,
        local_objects,
        current_timestamp,
        traj_method="dtw",
        alpha=0.5,
        threshold: Optional[float] = None,
        max_traj_loss: Optional[float] = None,
    ):
        """
        批量更新或註冊新物件，按類別分組處理
        :param local_objects: 要匹配的物件列表 [ObjectData, ...]
        :param current_timestamp: 當前時間戳
        :param traj_method: 軌跡比較方法
        :param alpha: 特徵權重
        :param threshold: 匹配閾值
        :return: None
        """
        self.clear_stale_objects(current_timestamp)
        if len(local_objects) == 0:
            return
        
        local_objects = self.trans_to_ObjectData(camera_id, local_objects)
        
        if camera_id not in self.local_global_mapping:
            self.local_global_mapping[camera_id] = dict()
        
        # 按類別分組
        objects_by_class = self._group_by_class(local_objects)
        
        # 分別處理每個類別
        for class_name, class_objects in objects_by_class.items():
            self._process_class_group(
                camera_id=camera_id,
                class_name=class_name,
                local_objects=class_objects,
                current_timestamp=current_timestamp,
                traj_method=traj_method,
                alpha=alpha,
                threshold=threshold,
                max_traj_loss=max_traj_loss,
            )
        
        # 更新映射
        self._update_mapping(camera_id, local_objects)
    
    def _group_by_class(self, objects):
        """按類別分組物件"""
        groups = {}
        for obj in objects:
            class_name = obj.class_name
            if class_name not in groups:
                groups[class_name] = []
            groups[class_name].append(obj)
        return groups
    
    def _process_class_group(
        self,
        camera_id,
        class_name,
        local_objects,
        current_timestamp,
        traj_method,
        alpha,
        threshold,
        max_traj_loss: Optional[float] = None,
    ):
        """
        處理單一類別的物件組

        :param camera_id: 攝影機ID
        :param class_name: 物件類別名稱
        :param local_objects: 該類別的局部物件列表
        :param current_timestamp: 當前時間戳
        :param traj_method: 軌跡比較方法
        :param alpha: 特徵權重
        :param threshold: 匹配閾值
        """
        # 只取出相同類別的全域物件
        global_objects_same_class = [
            obj for obj in self.global_objects.values()
            if obj.class_name == class_name
        ]

        # 如果沒有同類別的全域物件，處理為候選物件
        if len(global_objects_same_class) == 0:
            for obj in local_objects:
                self._handle_candidate(camera_id, obj, current_timestamp)
            return

        # 只在同類別內進行匹配
        ctx = {
            "camera_id": camera_id,
            "timestamp": current_timestamp,
            "backtrack_seconds": self.backtrack_seconds,
            "traj_method": traj_method,
            "alpha": alpha,
        }
        if max_traj_loss is not None:
            ctx["max_traj_loss"] = max_traj_loss

        match_results = self.matcher.run(
            local_objects,
            global_objects_same_class,
            cost_threshold=threshold,
            ctx=ctx,
        )

        dummy_idx = len(global_objects_same_class)

        for local_idx, global_idx, cost in match_results:
            local_obj = local_objects[local_idx]
            is_dummy = global_idx >= dummy_idx

            if not is_dummy and (threshold is None or cost < threshold):
                global_obj = global_objects_same_class[global_idx]
                if self._should_reject_by_distance(local_obj, global_obj):
                    self._handle_candidate(camera_id, local_obj, current_timestamp)
                    continue

                # 匹配成功：更新現有 global 物件
                gid = global_obj.global_id
                self.pending_updates[gid]["trajectories"].append(local_obj.trajectory)
                self.pending_updates[gid]["features"].append(local_obj.features)
                local_obj.global_id = gid
                # 從候選池中移除（如果存在）
                self.candidate_objects[camera_id].pop(local_obj.local_id, None)
                self.logger.info(f"[{camera_id}-{class_name}] Matched: local {local_obj.local_id} -> global {gid}, cost={cost:.2f}")
            else:
                # 匹配到 dummy 或成本過高：處理為候選物件
                self._handle_candidate(camera_id, local_obj, current_timestamp)
        
    def _handle_candidate(self, camera_id, local_obj, current_timestamp):
        """
        處理候選物件，實施多幀確認機制

        :param camera_id: 攝影機ID
        :param local_obj: 局部物件
        :param current_timestamp: 當前時間戳
        """
        local_id = local_obj.local_id

        # 如果候選物件已存在，增加計數
        if local_id in self.candidate_objects[camera_id]:
            candidate = self.candidate_objects[camera_id][local_id]
            candidate["hits"] += 1
            candidate["data"] = local_obj
            candidate["last_seen"] = current_timestamp

            # 達到確認閾值，提升為正式全局物件
            if candidate["hits"] >= self.confirmation_frames:
                self.register_new_object(local_obj, current_timestamp)
                self.candidate_objects[camera_id].pop(local_id, None)
                self.logger.info(f"[{local_obj.class_name}] Candidate promoted: {local_id} -> {local_obj.global_id} (hits={candidate['hits']})")
            else:
                # 暫時分配候選ID（負數）
                local_obj.global_id = f"candidate_{camera_id}_{local_id}"
                self.logger.debug(f"[{local_obj.class_name}] Candidate updated: {local_id}, hits={candidate['hits']}/{self.confirmation_frames}")
                # print(f"[{local_obj.class_name}] Candidate updated: {local_id}, hits={candidate['hits']}/{self.confirmation_frames}")
        else:
            # 新候選物件
            self.candidate_objects[camera_id][local_id] = {
                "hits": 1,
                "data": local_obj,
                "first_seen": current_timestamp,
                "last_seen": current_timestamp
            }
            local_obj.global_id = f"candidate_{camera_id}_{local_id}"
            self.logger.debug(f"[{local_obj.class_name}] New candidate: {local_id}, hits=1/{self.confirmation_frames}")
            # print(f"[{local_obj.class_name}] New candidate: {local_id}, hits=1/{self.confirmation_frames}")

    def register_new_object(self, local_object, timestamp=None):
        global_id = str(self.next_global_id)
        self.global_objects[self.next_global_id] = ObjectData(
            camera_id=local_object.camera_id,
            class_name=local_object.class_name,
            trajectory=local_object.trajectory,
            features=local_object.features,
            local_id=None,
            global_id=global_id,
            update_time=timestamp
        )
        local_object.global_id = global_id
        self.next_global_id += 1

    def _update_mapping(self, camera_id, local_objects):
        """輔助函數：更新 camera_id 對應的 local-global 映射。"""
        self.local_global_mapping[camera_id] = {obj.local_id: obj.global_id for obj in local_objects}

    def apply_pending_updates(self, current_timestamp: datetime):
        for global_id, update in self.pending_updates.items():
            global_obj = self.global_objects[int(global_id)]

            # 更新軌跡
            local_trajs = {
                f"source_{i}": traj for i, traj in enumerate(update["trajectories"])
            }
            updated_traj = TrajectoryUtils.update_global_trajectory(
                global_obj.trajectory,
                local_trajs
            )

            # 更新特徵
            features = update["features"]
            avg_feature = None

            if len(features) > 0 and not isinstance(features[0], type(None)):
                stacked = torch.stack(features)
                avg_feature = torch.mean(stacked, dim=0)
                
            # 一次性更新
            global_obj.trajectory = updated_traj
            if avg_feature is not None:
                global_obj.features = avg_feature
            global_obj.update_time = current_timestamp  # 同時更新時間戳


        self.pending_updates.clear()

    def clear_stale_objects(self, current_timestamp: datetime, clear_thres: timedelta=timedelta(seconds=60)):
        """
        清除 self.global_objects 中 update_time 超過 clear_thres 的項目

        :param clear_thres: timedelta 類型，設定多久沒更新就清除
        :param current_timestamp: 當前的 datetime 時間
        """
        del_list = []
        for global_id, data in self.global_objects.items():
            if current_timestamp - data.update_time > clear_thres:
                del_list.append(global_id)

        for global_id in del_list:
            self.global_objects.pop(global_id, None)

        # 同時清理候選物件池
        self.clear_stale_candidates(current_timestamp)

    def clear_stale_candidates(self, current_timestamp: datetime, candidate_thres: timedelta=timedelta(seconds=10)):
        """
        清除候選物件池中超過 candidate_thres 沒有更新的項目

        :param current_timestamp: 當前的 datetime 時間
        :param candidate_thres: timedelta 類型，設定候選物件多久沒更新就清除
        """
        for camera_id in list(self.candidate_objects.keys()):
            del_list = []
            for local_id, candidate in self.candidate_objects[camera_id].items():
                if current_timestamp - candidate["last_seen"] > candidate_thres:
                    del_list.append(local_id)

            for local_id in del_list:
                self.candidate_objects[camera_id].pop(local_id, None)

            # 如果該相機的候選池已清空，移除該相機的條目
            if len(self.candidate_objects[camera_id]) == 0:
                self.candidate_objects.pop(camera_id, None)

    def _should_reject_by_distance(self, local_obj: ObjectData, global_obj: ObjectData) -> bool:
        if self.distance_threshold_m is None:
            return False
        if self.map_scale is None:
            if not self._distance_warning_logged:
                self.logger.warning("距離閾值已設定但 map_scale 不可用，將略過距離檢查")
                self._distance_warning_logged = True
            return False
        distance = self._compute_distance_meters(local_obj, global_obj)
        
        if distance is None:
            return False
        if distance > self.distance_threshold_m:
            self.logger.debug(
                f"[{local_obj.class_name}] 距離 {distance:.2f}m 超過閾值 {self.distance_threshold_m:.2f}m"
            )
            return True
        self.logger.debug(
                f"[{local_obj.class_name}] 距離 {distance:.2f}m 未超過閾值 {self.distance_threshold_m:.2f}m"
            )
        return False

    def _compute_distance_meters(self, local_obj: ObjectData, global_obj: ObjectData) -> Optional[float]:
        local_xy = self._extract_latest_xy(local_obj)
        global_xy = self._extract_latest_xy(global_obj)
        if local_xy is None or global_xy is None:
            return None
        dx = local_xy[0] - global_xy[0]
        dy = local_xy[1] - global_xy[1]
        scale_x = self.map_scale.get("meters_per_pixel_x") if self.map_scale else None
        scale_y = self.map_scale.get("meters_per_pixel_y") if self.map_scale else None
        if scale_x is None or scale_y is None:
            return None
        return math.hypot(dx * scale_x, dy * scale_y)

    @staticmethod
    def _extract_latest_xy(obj: ObjectData) -> Optional[tuple]:
        trajectory = getattr(obj, "trajectory", None)
        if not trajectory:
            return None
        last_entry = trajectory[-1]
        if len(last_entry) < 3:
            return None
        try:
            x = float(last_entry[1])
            y = float(last_entry[2])
        except (TypeError, ValueError):
            return None
        return (x, y)
