import asyncio
from typing import Optional
from dataclasses import dataclass, field
from motion_detector import MotionDetector
from roi_manager import ROIManager


@dataclass
class AppState:
    """Central application state container"""
    detector: Optional[MotionDetector] = None
    roi_manager: Optional[ROIManager] = None
    current_camera_url: str = ""
    shutdown_event: asyncio.Event = field(default_factory=asyncio.Event)
    
    def get_detector(self) -> Optional[MotionDetector]:
        """Get current detector instance"""
        return self.detector
    
    def set_detector(self, detector: MotionDetector) -> None:
        """Update detector instance"""
        self.detector = detector
    
    def get_roi_manager(self) -> Optional[ROIManager]:
        """Get current ROI manager"""
        return self.roi_manager
    
    def set_roi_manager(self, roi_manager: ROIManager) -> None:
        """Update ROI manager"""
        self.roi_manager = roi_manager

# Global instance (singleton)
app_state = AppState()