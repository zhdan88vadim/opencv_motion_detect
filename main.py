import os
import signal
import threading
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from config import CAMERAS, DEFAULT_CAMERA, logger, config
from roi_manager import ROIManager
from motion_detector import MotionDetector
from api_routes import setup_routes
from app_state import app_state


# ===== Lifespan =====
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        default_config = CAMERAS[DEFAULT_CAMERA]
        app_state.current_camera_url = default_config["url"]
        
        # Initialize ROI Manager
        app_state.roi_manager = ROIManager()
        
        # Initialize Detector
        app_state.detector = MotionDetector(
            motion_threshold=200,
            min_area=5,
            rtsp_url=app_state.current_camera_url,
            has_audio=default_config.get("has_audio", True),
            camera_name=DEFAULT_CAMERA,
            roi_manager=app_state.roi_manager
        )
        app_state.detector.start()

        
        logger.info(f"🚀 Server started with camera: {DEFAULT_CAMERA}")
        logger.info(f"📐 ROI Manager: Initialized")
        
        yield
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    finally:
        # Shutdown
        if app_state.detector:
            app_state.detector.stop()
        logger.info("✅ Server shutdown complete")


# ===== Create FastAPI App =====
app = FastAPI(
    title="Motion Detection API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup routes - pass app_state instead of individual getters
setup_routes(app, app_state)


# ===== Signal Handler =====
def signal_handler(sig, frame):
    """Handle shutdown signals"""
    if config.shutdown_flag:
        os._exit(1)
    
    config.shutdown_flag = True
    app_state.shutdown_event.set()
    
    logger.info("🛑 Shutting down...")
    
    def do_shutdown():
        if app_state.detector:
            try:
                app_state.detector.stop()
            except Exception as e:
                logger.error(f"Error stopping detector: {e}")
        logger.info("✅ Shutdown complete")
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
        if app_state.detector:
            app_state.detector.stop()