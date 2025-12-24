"""
Trajectory Analyzer
Handles trajectory analysis including in/out predictions and trajectory filtering
"""

import numpy as np
from typing import List, Dict, Tuple
from integration.mcmot.utils.logger import get_logger
from shapely.geometry import Polygon, Point


class TrajectoryAnalyzer:
    """Analyzes trajectories and provides insights for object behavior"""
    
    def __init__(self, config):
        """
        Initialize trajectory analyzer
        
        Args:
            config: 配置物件
        """
        self.logger = get_logger(
            name="trajectory_analyzer",
            log_file="mcmot_coordinator"
        )
        self.config = config
    
    def filter_objects_by_ignore_areas(self, objects: List[Dict], ignore_areas: List[List[Tuple[float, float]]]) -> List[Dict]:
        """
        Filter out objects that fall within ignore areas
        
        Args:
            objects: List of detected objects
            ignore_areas: List of polygon boundaries to ignore
            
        Returns:
            List of objects outside ignore areas
        """
        if ignore_areas is None or len(ignore_areas) == 0:
            return objects
        
        try:
            # Create polygon objects from ignore areas
            polygon_objects = []
            for area in ignore_areas:
                if area is not None:
                    try:
                        # 直接嘗試創建 Polygon（zone_utils 已經處理了格式問題）
                        polygon_objects.append(Polygon(area))
                    except Exception as e:
                        self.logger.warning(f"Failed to create polygon from area: {e}")
                        continue
            
            filtered_objects = []
            
            for obj in objects:
                bbox = obj.get('bbox')
                if bbox is None:
                    continue
                
                # Calculate object center point
                center_point = self._get_bbox_center(bbox)
                point = Point(center_point)
                
                # Check if point is outside all ignore areas
                if not any(poly.contains(point) for poly in polygon_objects):
                    filtered_objects.append(obj)
            
            return filtered_objects
            
        except Exception as e:
            self.logger.error(f"Error filtering objects by ignore areas: {e}")
            return objects
    
    def analyze_trajectory_quality(self, trajectory: List[Tuple[float, float]]) -> Dict[str, float]:
        """
        Analyze the quality of a trajectory
        
        Args:
            trajectory: List of (x, y) coordinate points
            
        Returns:
            Dictionary containing quality metrics
        """
        if len(trajectory) < 2:
            return {
                'length': 0,
                'smoothness': 0.0,
                'linearity': 0.0,
                'coverage': 0.0
            }
        
        try:
            trajectory_array = np.array(trajectory)
            
            # Calculate trajectory length
            distances = np.linalg.norm(np.diff(trajectory_array, axis=0), axis=1)
            total_length = np.sum(distances)
            
            # Calculate smoothness (inverse of acceleration variance)
            if len(trajectory) >= 3:
                accelerations = np.diff(distances)
                smoothness = 1.0 / (1.0 + np.var(accelerations))
            else:
                smoothness = 1.0
            
            # Calculate linearity (how close to straight line)
            if total_length > 0:
                direct_distance = np.linalg.norm(trajectory_array[-1] - trajectory_array[0])
                linearity = direct_distance / total_length
            else:
                linearity = 0.0
            
            # Calculate coverage (bounding box area)
            min_coords = np.min(trajectory_array, axis=0)
            max_coords = np.max(trajectory_array, axis=0)
            coverage = np.prod(max_coords - min_coords)
            
            return {
                'length': total_length,
                'smoothness': smoothness,
                'linearity': linearity,
                'coverage': coverage
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing trajectory quality: {e}")
            return {
                'length': 0,
                'smoothness': 0.0,
                'linearity': 0.0,
                'coverage': 0.0
            }
    
    def predict_future_positions(self, trajectory: List[Tuple[float, float]], 
                               steps: int = 5) -> List[Tuple[float, float]]:
        """
        Predict future positions based on current trajectory
        
        Args:
            trajectory: List of (x, y) coordinate points
            steps: Number of future steps to predict
            
        Returns:
            List of predicted future positions
        """
        if len(trajectory) < 2:
            return []
        
        try:
            trajectory_array = np.array(trajectory)
            
            # Use simple linear extrapolation based on last few points
            if len(trajectory) >= 3:
                # Use last 3 points for velocity estimation
                recent_points = trajectory_array[-3:]
                velocity = np.mean(np.diff(recent_points, axis=0), axis=0)
            else:
                # Use last 2 points
                velocity = trajectory_array[-1] - trajectory_array[-2]
            
            # Predict future positions
            predictions = []
            last_point = trajectory_array[-1]
            
            for i in range(1, steps + 1):
                future_point = last_point + velocity * i
                predictions.append(tuple(future_point))
            
            return predictions
            
        except Exception as e:
            self.logger.error(f"Error predicting future positions: {e}")
            return []
    
    def _calculate_distance(self, point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
        """Calculate Euclidean distance between two points"""
        return np.sqrt(np.sum((np.array(point1) - np.array(point2)) ** 2))
    
    def _get_bbox_center(self, bbox: List[float]) -> Tuple[float, float]:
        """
        Calculate center point of bounding box
        
        Args:
            bbox: Bounding box [x1, y1, x2, y2]
            
        Returns:
            Center point (x, y)
        """
        # Use bottom center for vessel tracking (better representation)
        center_x = (bbox[0] + bbox[2]) / 2
        center_y = bbox[3]  # Bottom of bounding box
        return (center_x, center_y)
    
    def update_reference_point(self, new_reference_point: Tuple[float, float]) -> None:
        """
        Update the reference point for direction analysis
        
        Args:
            new_reference_point: New reference point coordinates
        """
        self.reference_point = new_reference_point
        self.logger.info(f"Updated reference point to {new_reference_point}")
    
    def update_distance_threshold(self, new_threshold: float) -> None:
        """
        Update the distance threshold for direction classification
        
        Args:
            new_threshold: New distance threshold
        """
        self.distance_threshold = new_threshold
        self.logger.info(f"Updated distance threshold to {new_threshold}")