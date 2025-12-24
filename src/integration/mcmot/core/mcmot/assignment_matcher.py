import numpy as np
from scipy.optimize import linear_sum_assignment

class AssignmentMatcher:
    PAD_COST = 1e6

    def preprocess(self, data):
        raise NotImplementedError()

    def compute_cost_matrix(self, data_A, data_B):
        raise NotImplementedError()

    def postprocess(self, matched_pairs, data_A, data_B):
        raise NotImplementedError()

    @staticmethod
    def pad_cost_matrix(cost_matrix, pad_value):
        n_rows, n_cols = cost_matrix.shape
        size = max(n_rows, n_cols)
        padded = np.full((size, size), pad_value)
        padded[:n_rows, :n_cols] = cost_matrix
        return padded, n_rows, n_cols

    @staticmethod
    def match(cost_matrix):
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        return list(zip(row_ind, col_ind))

    def run(self, data_A, data_B, cost_threshold=None):
        data_A = self.preprocess(data_A)
        data_B = self.preprocess(data_B)
        cost_matrix = self.compute_cost_matrix(data_A, data_B)
        padded_matrix, n_A, n_B = self.pad_cost_matrix(cost_matrix, self.PAD_COST)
        matches = self.match(padded_matrix)
        filtered_matches = []
        for i, j in matches:
            if i >= n_A or j >= n_B:
                continue  # matched to dummy
            if cost_matrix[i, j] > (cost_threshold or self.PAD_COST):
                continue
            filtered_matches.append((i, j))
        return self.postprocess(filtered_matches, data_A, data_B)
