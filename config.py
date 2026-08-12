import os
import logging
from typing import Dict

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConfigManager:

    def __init__(self):
        # Set OpenCV environment variables for stability
        os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp|timeout;5000|max_delay;500'
        os.environ['OPENCV_VIDEOIO_DEBUG'] = '0'
        os.environ['OPENCV_FFMPEG_DEBUG'] = '0'

        # Camera configurations with audio support flag
        self.CAMERAS = {
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

        self.DEFAULT_CAMERA = list(self.CAMERAS.keys())[0]

        # Video recording settings
        self.RECORDINGS_DIR = "recordings"
        self.RECORD_BUFFER_SECONDS = 2
        self.RECORD_AFTER_SECONDS = 3
        self.MIN_RECORD_SECONDS = 3
        self.MAX_RECORD_SECONDS = 300
        self.DISPLAY_WIDTH = 800
        self.DISPLAY_HEIGHT = 600

        # ROI Settings
        self.ROI_SETTINGS_FILE = "roi_settings.json"
        self.DEFAULT_ROI = {"x": 0, "y": 0, "width": 1.0, "height": 1.0, "enabled": False}

        # changeable settings
        self._recording_enable = False
        self._detection_enabled = True
        self._shutdown_flag = False

    @property
    def recording_enable(self):
        return self._recording_enable

    @recording_enable.setter
    def recording_enable(self, value):
        self._recording_enable = bool(value)

    @property
    def detection_enabled(self):
        return self._detection_enabled
    
    @detection_enabled.setter
    def detection_enabled(self, value):
        self._detection_enabled = bool(value)
        logger.info(f"Detection enabled: {self._detection_enabled}")
    
    @property
    def shutdown_flag(self):
        return self._shutdown_flag
    
    @shutdown_flag.setter
    def shutdown_flag(self, value):
        self._shutdown_flag = bool(value)
        if self._shutdown_flag:
            logger.info("Shutdown flag set")

# Создаем глобальный экземпляр
config = ConfigManager()

# Экспортируем для удобства
CAMERAS = config.CAMERAS
DEFAULT_CAMERA = config.DEFAULT_CAMERA
RECORDINGS_DIR = config.RECORDINGS_DIR
RECORD_BUFFER_SECONDS = config.RECORD_BUFFER_SECONDS
RECORD_AFTER_SECONDS = config.RECORD_AFTER_SECONDS
MIN_RECORD_SECONDS = config.MIN_RECORD_SECONDS
MAX_RECORD_SECONDS = config.MAX_RECORD_SECONDS
DISPLAY_WIDTH = config.DISPLAY_WIDTH
DISPLAY_HEIGHT = config.DISPLAY_HEIGHT
ROI_SETTINGS_FILE = config.ROI_SETTINGS_FILE
DEFAULT_ROI = config.DEFAULT_ROI
logger = logging.getLogger(__name__)                