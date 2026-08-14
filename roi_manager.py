import json
import os
import threading
import cv2
import numpy as np
from typing import Dict, Any, Optional, List, Union

from config import DEFAULT_ROI, ROI_SETTINGS_FILE, CAMERAS, logger
from models import ROISettings


class ROIManager:
    """Manages ROI settings per camera"""
    
    def __init__(self, settings_file: str = ROI_SETTINGS_FILE) -> None:
        self.settings_file: str = settings_file
        self.rois: Dict[str, ROISettings] = {}
        self.lock: threading.Lock = threading.Lock()
        self.load_settings()
    
    def load_settings(self) -> None:
        """Load ROI settings from file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    data: Dict[str, Any] = json.load(f)
                    # Convert dict to ROISettings
                    self.rois = {
                        k: ROISettings(**v) for k, v in data.items()
                    }
                logger.info(f"Loaded ROI settings for {len(self.rois)} cameras")
            else:
                # Initialize with default ROIs for all cameras
                for camera_name in CAMERAS.keys():
                    self.rois[camera_name] = DEFAULT_ROI.model_copy()
                self.save_settings()
        except Exception as e:
            logger.error(f"Error loading ROI settings: {e}")
            self.rois = {}
            for camera_name in CAMERAS.keys():
                self.rois[camera_name] = DEFAULT_ROI.model_copy()
    
    def save_settings(self) -> None:
        """Save ROI settings to file"""
        try:
            # Convert ROISettings objects to dict for JSON serialization
            data = {k: v.model_dump() for k, v in self.rois.items()}
            with open(self.settings_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info("ROI settings saved")
        except Exception as e:
            logger.error(f"Error saving ROI settings: {e}")
    
    def get_roi(self, camera_name: str) -> ROISettings:
        """Get ROI for a specific camera"""
        with self.lock:
            if camera_name not in self.rois:
                self.rois[camera_name] = DEFAULT_ROI.model_copy()
                self.save_settings()
            return self.rois[camera_name]
    
    def set_roi(self, camera_name: str, roi: ROISettings) -> None:
        """Set ROI for a specific camera"""
        with self.lock:
            normalized_roi = ROISettings(
                x=max(0.0, min(1.0, roi.x)),
                y=max(0.0, min(1.0, roi.y)),
                width=max(0.0, min(1.0, roi.width)),
                height=max(0.0, min(1.0, roi.height)),
                enabled=roi.enabled
            )
            
            # Ensure ROI doesn't go outside bounds
            if normalized_roi.x + normalized_roi.width > 1.0:
                normalized_roi.width = 1.0 - normalized_roi.x
            if normalized_roi.y + normalized_roi.height > 1.0:
                normalized_roi.height = 1.0 - normalized_roi.y
            
            self.rois[camera_name] = normalized_roi
            self.save_settings()
            logger.info(f"Updated ROI for camera: {camera_name} - {normalized_roi}")
    
    def reset_roi(self, camera_name: str) -> None:
        """Reset ROI to default (full frame) for a camera"""
        with self.lock:
            self.rois[camera_name] = DEFAULT_ROI.model_copy()
            self.save_settings()
            logger.info(f"Reset ROI for camera: {camera_name}")
    
    def apply_roi_to_frame(self, frame: np.ndarray, camera_name: str) -> np.ndarray:
        """Apply ROI mask to frame if enabled"""
        roi: ROISettings = self.get_roi(camera_name)
        if not roi.enabled:
            return frame
        
        height, width = frame.shape[:2]
        x = int(roi.x * width)
        y = int(roi.y * height)
        roi_width = int(roi.width * width)
        roi_height = int(roi.height * height)
        
        # Create mask
        mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        mask[y:y+roi_height, x:x+roi_width] = 255
        
        # Apply mask
        masked_frame = cv2.bitwise_and(frame, frame, mask=mask)
        
        # Draw ROI rectangle on the frame for visualization
        cv2.rectangle(frame, (x, y), (x+roi_width, y+roi_height), (0, 255, 255), 2)
        cv2.putText(frame, "ROI", (x+5, y+25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        return masked_frame