import os
import signal
import threading
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import (
    CAMERAS, DEFAULT_CAMERA, logger, config
)
from roi_manager import ROIManager
from motion_detector import MotionDetector
from api_routes import setup_routes

# Global state
detector = None
shutdown_event = asyncio.Event()
current_camera_url = CAMERAS[DEFAULT_CAMERA]["url"]

# Создаем ЕДИНСТВЕННЫЙ экземпляр ROI Manager
roi_manager = ROIManager()


# ===== Функции для передачи в api_routes =====
def get_detector():
    """Getter for detector instance"""
    global detector
    return detector


def get_roi_manager():
    """Getter for ROI manager instance"""
    global roi_manager
    return roi_manager


# ===== Lifespan =====
@asynccontextmanager
async def lifespan(app: FastAPI):
    global detector, current_camera_url
    
    default_config = CAMERAS[DEFAULT_CAMERA]
    current_camera_url = default_config["url"]
    
    # Создаем детектор с roi_manager
    detector = MotionDetector(
        motion_threshold=200, 
        min_area=5, 
        rtsp_url=current_camera_url,
        has_audio=default_config.get("has_audio", True),
        camera_name=DEFAULT_CAMERA,
        roi_manager=roi_manager
    )
    detector.start()
    
    print("🌐 Server starting with FastAPI")
    print(f"📷 Default camera: {DEFAULT_CAMERA}")
    print(f"🔊 Audio: {'Enabled' if default_config.get('has_audio', True) else 'Disabled'}")
    print(f"📐 ROI Manager: Initialized")
    yield
    if detector:
        detector.stop()

app = FastAPI(lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настраиваем роуты
setup_routes(app, get_detector, get_roi_manager)


# ===== Signal Handler =====
def signal_handler(sig, frame):
    """Handle shutdown signals"""
    global  detector
    if config.shutdown_flag:
        os._exit(1)
    
    config.shutdown_flag = True
    shutdown_event.set()
    
    print("\n🛑 Shutting down...")
    
    def do_shutdown():
        global detector
        if detector:
            try:
                detector.stop()
            except Exception as e:
                logger.error(f"Error stopping detector: {e}")
        print("✅ Shutdown complete")
        os._exit(0)
    
    threading.Thread(target=do_shutdown, daemon=True).start()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8080,
            log_level="info",
            access_log=True,
            timeout_keep_alive=30,
            timeout_graceful_shutdown=5,
            loop="asyncio",
            reload=True,
        )
    except KeyboardInterrupt:
        signal_handler(None, None)
    finally:
        if detector:
            detector.stop()