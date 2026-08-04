import json
import os
import threading
import logging
import cv2
import numpy as np
from typing import Dict

from config import DEFAULT_ROI, ROI_SETTINGS_FILE, CAMERAS, logger

class ROIManager:
    """Manages ROI settings per camera"""
    def __init__(self, settings_file=ROI_SETTINGS_FILE):
        self.settings_file = settings_file
        self.rois: Dict[str, Dict] = {}
        self.lock = threading.Lock()
        self.load_settings()
    
    def load_settings(self):
        """Load ROI settings from file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    self.rois = json.load(f)
                logger.info(f"Loaded ROI settings for {len(self.rois)} cameras")
            else:
                # Initialize with default ROIs for all cameras
                for camera_name in CAMERAS.keys():
                    self.rois[camera_name] = DEFAULT_ROI.copy()
                self.save_settings()
        except Exception as e:
            logger.error(f"Error loading ROI settings: {e}")
            self.rois = {}
            for camera_name in CAMERAS.keys():
                self.rois[camera_name] = DEFAULT_ROI.copy()
    
    def save_settings(self):
        """Save ROI settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.rois, f, indent=2)
            logger.info("ROI settings saved")
        except Exception as e:
            logger.error(f"Error saving ROI settings: {e}")
    
    def get_roi(self, camera_name: str) -> Dict:
        """Get ROI for a specific camera"""
        with self.lock:
            if camera_name not in self.rois:
                self.rois[camera_name] = DEFAULT_ROI.copy()
                self.save_settings()
            return self.rois[camera_name].copy()
    
    def set_roi(self, camera_name: str, roi: Dict):
        """Set ROI for a specific camera"""
        with self.lock:
            # Validate ROI
            required_keys = ['x', 'y', 'width', 'height', 'enabled']
            for key in required_keys:
                if key not in roi:
                    raise ValueError(f"Missing required key: {key}")
            
            # Normalize values
            roi['x'] = max(0.0, min(1.0, float(roi['x'])))
            roi['y'] = max(0.0, min(1.0, float(roi['y'])))
            roi['width'] = max(0.0, min(1.0, float(roi['width'])))
            roi['height'] = max(0.0, min(1.0, float(roi['height'])))
            roi['enabled'] = bool(roi['enabled'])
            
            # Ensure ROI doesn't go outside bounds
            if roi['x'] + roi['width'] > 1.0:
                roi['width'] = 1.0 - roi['x']
            if roi['y'] + roi['height'] > 1.0:
                roi['height'] = 1.0 - roi['y']
            
            self.rois[camera_name] = roi
            self.save_settings()
            logger.info(f"Updated ROI for camera: {camera_name} - {roi}")
    
    def reset_roi(self, camera_name: str):
        """Reset ROI to default (full frame) for a camera"""
        with self.lock:
            self.rois[camera_name] = DEFAULT_ROI.copy()
            self.save_settings()
            logger.info(f"Reset ROI for camera: {camera_name}")
    
    def apply_roi_to_frame(self, frame: np.ndarray, camera_name: str) -> np.ndarray:
        """Apply ROI mask to frame if enabled"""
        roi = self.get_roi(camera_name)
        if not roi['enabled']:
            return frame
        
        height, width = frame.shape[:2]
        x = int(roi['x'] * width)
        y = int(roi['y'] * height)
        roi_width = int(roi['width'] * width)
        roi_height = int(roi['height'] * height)
        
        # Create mask
        mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        mask[y:y+roi_height, x:x+roi_width] = 255
        
        # Apply mask
        masked_frame = cv2.bitwise_and(frame, frame, mask=mask)
        
        # Draw ROI rectangle on the frame for visualization
        cv2.rectangle(frame, (x, y), (x+roi_width, y+roi_height), (0, 255, 255), 2)
        cv2.putText(frame, "ROI", (x+5, y+25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        return masked_frame