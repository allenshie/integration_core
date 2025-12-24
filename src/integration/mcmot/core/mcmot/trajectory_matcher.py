# matcher_adapter.py

from typing import Optional

from .assignment_matcher import AssignmentMatcher

class TrajectoryMatcher(AssignmentMatcher):
    DEFAULT_MAX_TRAJ_LOSS = 1000.0

    def __init__(self, max_traj_loss: Optional[float] = None, match_threshold: Optional[float] = None):
        super().__init__()
        self.max_traj_loss = max_traj_loss or self.DEFAULT_MAX_TRAJ_LOSS
        self.match_threshold = match_threshold

    def preprocess(self, data, ctx=None):
        return data  # 無需前處理

    def compute_cost_matrix(self, local_objs, global_objs, ctx=None):
        from .cost_matrix import CostMatrix
        return CostMatrix.compute_cost_matrix(
            local_objs,
            global_objs,
            ctx["timestamp"],
            ctx.get("backtrack_seconds", 5),
            ctx.get("traj_method", "dtw"),
            ctx.get("alpha", 0.5),
            ctx.get("max_traj_loss", self.max_traj_loss),
        )

    def postprocess(self, matched_pairs, padded_matrix):
        return [(i, j, padded_matrix[i, j]) for i, j in matched_pairs]

    def run(self, local_objs, global_objs, cost_threshold=None, ctx=None):
        local_objs = self.preprocess(local_objs, ctx)
        global_objs = self.preprocess(global_objs, ctx)
        cost_matrix = self.compute_cost_matrix(local_objs, global_objs, ctx)
        padded_matrix, n_A, n_B = self.pad_cost_matrix(cost_matrix, self.PAD_COST)
        matches = self.match(padded_matrix)
        
        # 保留所有匹配結果，包括 dummy 匹配
        # 讓上層邏輯決定如何處理未匹配的物件
        filtered_matches = []
        threshold = cost_threshold if cost_threshold is not None else self.match_threshold
        for i, j in matches:
            # 只保留 local 物件在有效範圍內的匹配
            if i < n_A:
                if j < n_B and threshold is not None and padded_matrix[i, j] > threshold:
                    continue
                filtered_matches.append((i, j))

        return self.postprocess(filtered_matches, padded_matrix)
