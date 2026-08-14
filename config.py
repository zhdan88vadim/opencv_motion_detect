import os
import logging
from typing import Dict, Union, Optional

from models import ROISettings

logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)


class ConfigManager:
    def __init__(self) -> None:
        # Set OpenCV environment variables for stability
        os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp|timeout;5000|max_delay;500'
        os.environ['OPENCV_VIDEOIO_DEBUG'] = '0'
        os.environ['OPENCV_FFMPEG_DEBUG'] = '0'

        # Camera configurations with audio support flag
        self.CAMERAS: Dict[str, Dict[str, Union[str, bool]]] = {
            "Balcony Camera": {
                "url": "rtsp://192.168.0.102:8554/balcony_camera_hero_4mp_wifi_h264",
                "has_audio": True
            },
            "Kitchen": {
                "url": "rtsp://192.168.0.102:8554/h1_long_1_h264",
                "has_audio": True
            },
            "H40": {
                "url": "rtsp://192.168.0.102:8554/h40_long_1_h264",
                "has_audio": True
            },
            "Hik_vision": {
                "url": "rtsp://192.168.0.102:8554/hikvision_room_sub",
                "has_audio": False
            },
            "Children Room": {
                "url": "rtsp://192.168.0.102:8554/h2_long_1_wifi_h264",
                "has_audio": True
            },
            "Corridor": {
                "url": "rtsp://192.168.0.102:8554/ESP32-CAM_video36",
                "has_audio": False
            },
        }

        self.DEFAULT_CAMERA: str = list(self.CAMERAS.keys())[0]

        # Video recording settings
        self.RECORDINGS_DIR: str = "recordings"
        self.RECORD_BUFFER_SECONDS: int = 2
        self.RECORD_AFTER_SECONDS: int = 3
        self.MIN_RECORD_SECONDS: int = 3
        self.MAX_RECORD_SECONDS: int = 300
        self.DISPLAY_WIDTH: int = 800
        self.DISPLAY_HEIGHT: int = 600

        self.ROI_SETTINGS_FILE: str = "roi_settings.json"
        self.DEFAULT_ROI: ROISettings = ROISettings(
            x=0.0,
            y=0.0,
            width=1.0,
            height=1.0,
            enabled=False
        )

        # changeable settings
        self._recording_enable: bool = False
        self._detection_enabled: bool = True
        self._shutdown_flag: bool = False

    @property
    def recording_enable(self) -> bool:
        return self._recording_enable

    @recording_enable.setter
    def recording_enable(self, value: bool) -> None:
        self._recording_enable = bool(value)

    @property
    def detection_enabled(self) -> bool:
        return self._detection_enabled
    
    @detection_enabled.setter
    def detection_enabled(self, value: bool) -> None:
        self._detection_enabled = bool(value)
        logger.info(f"Detection enabled: {self._detection_enabled}")
    
    @property
    def shutdown_flag(self) -> bool:
        return self._shutdown_flag
    
    @shutdown_flag.setter
    def shutdown_flag(self, value: bool) -> None:
        self._shutdown_flag = bool(value)
        if self._shutdown_flag:
            logger.info("Shutdown flag set")

# Create a global instance
config: ConfigManager = ConfigManager()

# Export for convenience
CAMERAS: Dict[str, Dict[str, Union[str, bool]]] = config.CAMERAS
DEFAULT_CAMERA: str = config.DEFAULT_CAMERA
RECORDINGS_DIR: str = config.RECORDINGS_DIR
RECORD_BUFFER_SECONDS: int = config.RECORD_BUFFER_SECONDS
RECORD_AFTER_SECONDS: int = config.RECORD_AFTER_SECONDS
MIN_RECORD_SECONDS: int = config.MIN_RECORD_SECONDS
MAX_RECORD_SECONDS: int = config.MAX_RECORD_SECONDS
DISPLAY_WIDTH: int = config.DISPLAY_WIDTH
DISPLAY_HEIGHT: int = config.DISPLAY_HEIGHT
ROI_SETTINGS_FILE: str = config.ROI_SETTINGS_FILE
DEFAULT_ROI: ROISettings = config.DEFAULT_ROI