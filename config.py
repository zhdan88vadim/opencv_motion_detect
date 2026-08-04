import os
import logging
from typing import Dict

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set OpenCV environment variables for stability
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp|timeout;5000|max_delay;500'
os.environ['OPENCV_VIDEOIO_DEBUG'] = '0'
os.environ['OPENCV_FFMPEG_DEBUG'] = '0'

# Camera configurations with audio support flag
CAMERAS = {
    "Balcony Camera": {
        "url": "rtsp://192.168.0.102:8554/balcony_camera_hero_4mp_wifi_h264",
        "has_audio": True
    },
    "Kitchen": {
        "url": "rtsp://192.168.0.102:8554/h1_long_1_h264",
        "has_audio": True
    },
    "Zorayna": {
        "url": "rtsp://192.168.0.102:8554/h40_long_1_h264",
        "has_audio": True
    },
    "Zlata Quick": {
        "url": "rtsp://192.168.0.102:8554/hikvision_room_sub",
        "has_audio": False
    },
    "Children Room": {
        "url": "rtsp://192.168.0.102:8554/h2_long_1_wifi_h264",
        "has_audio": True
    },
    "Koridor": {
        "url": "rtsp://192.168.0.102:8554/ESP32-CAM_video36",
        "has_audio": False
    },
}

DEFAULT_CAMERA = list(CAMERAS.keys())[0]

# Video recording settings
RECORDINGS_DIR = "recordings"
RECORD_BUFFER_SECONDS = 2
RECORD_AFTER_SECONDS = 3
MIN_RECORD_SECONDS = 3
MAX_RECORD_SECONDS = 300
RECORDING_ENABLED = False
DETECTION_ENABLED = True

shutdown_flag = False

# ROI Settings
ROI_SETTINGS_FILE = "roi_settings.json"
DEFAULT_ROI = {"x": 0, "y": 0, "width": 1.0, "height": 1.0, "enabled": False}