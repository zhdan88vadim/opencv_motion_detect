import os
import time
import glob
import asyncio
import queue
import gc
from datetime import datetime
from typing import Optional, Callable

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

from config import (
    CAMERAS, DEFAULT_CAMERA, RECORDINGS_DIR, logger, config
)
from html_template import HTML_TEMPLATE
from models import CameraROIRequest
from motion_detector import MotionDetector
from roi_manager import ROIManager

# Глобальное состояние
detector: Optional[MotionDetector] = None
current_camera_url: str = CAMERAS[DEFAULT_CAMERA]["url"]
roi_manager: Optional[ROIManager] = None


def setup_routes(
    app: FastAPI,
    get_detector: Callable[[], Optional[MotionDetector]],
    get_roi_manager: Callable[[], Optional[ROIManager]],
):
    """
    Setup all API routes
    
    Args:
        app: FastAPI приложение
        get_detector: Функция для получения текущего детектора
        get_roi_manager: Функция для получения ROI менеджера
    """
    
    # Импортируем здесь, чтобы избежать циклических импортов
    from motion_detector import MotionDetector
    
    @app.get("/")
    async def index():
        camera_options = ""
        for name, config in CAMERAS.items():
            selected = "selected" if name == DEFAULT_CAMERA else ""
            has_audio = "true" if config.get("has_audio", True) else "false"
            url = config["url"]
            camera_options += f'<option value="{url}" data-has-audio="{has_audio}" data-camera-name="{name}" {selected}>{name}</option>'
        
        html = HTML_TEMPLATE.replace('__CAMERA_OPTIONS__', camera_options)
        return HTMLResponse(html)
    
    @app.get("/stream.mjpg")
    async def stream_mjpeg(request: Request):
        detector = get_detector()
        threshold = request.query_params.get('threshold', 200)
        min_area = request.query_params.get('min_area', 5)
        
        if detector:
            detector.update_params(int(threshold), int(min_area))
        
        async def generate():
            while detector and detector.running:
                try:
                    jpeg = detector.get_jpeg()
                    if jpeg:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n'
                               b'Content-Length: ' + str(len(jpeg)).encode() + b'\r\n\r\n'
                               + jpeg + b'\r\n')
                    await asyncio.sleep(1/15)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"MJPEG stream error: {e}")
                    break
        
        return StreamingResponse(
            generate(),
            media_type="multipart/x-mixed-replace; boundary=frame"
        )
    
    @app.get("/events")
    async def sse_events():
        """Server-Sent Events endpoint for real-time status updates"""
        detector = get_detector()
        q = asyncio.Queue(maxsize=10)
        
        if detector:
            with detector.sse_lock:
                detector.sse_clients.append(q)
        
        async def event_generator():
            try:
                while detector and detector.running:
                    try:
                        data = await asyncio.wait_for(q.get(), timeout=1.0)
                        yield f"data: {data}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.error(f"SSE generator error: {e}")
                        break
            finally:
                if detector:
                    with detector.sse_lock:
                        if q in detector.sse_clients:
                            try:
                                detector.sse_clients.remove(q)
                            except ValueError:
                                pass
                while not q.empty():
                    try:
                        q.get_nowait()
                    except:
                        break
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    
    @app.get("/audio.wav")
    async def audio_stream():
        detector = get_detector()
        if not detector or not hasattr(detector, 'audio_streamer'):
            return JSONResponse({"error": "Audio streamer not available"}, status_code=500)
        
        streamer = detector.audio_streamer
        audio_queue = streamer.subscribe_client()
        
        async def generate():
            try:
                yield streamer.wav_header
                
                while detector and detector.running:
                    try:
                        chunk = await asyncio.get_event_loop().run_in_executor(
                            None, lambda: audio_queue.get(timeout=0.3)
                        )
                        if chunk:
                            yield chunk
                    except queue.Empty:
                        continue
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.error(f"Audio stream error: {e}")
                        break
            finally:
                streamer.unsubscribe_client(audio_queue)
        
        return StreamingResponse(
            generate(),
            media_type="audio/wav",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Pragma": "no-cache",
                "Expires": "0",
            }
        )
    
    @app.post("/switch_camera")
    async def switch_camera(request: Request):
        global current_camera_url
        try:
            data = await request.json()
            new_url = data.get('url')
            camera_name = data.get('name', 'Unknown')
            has_audio = data.get('has_audio', True)
            roi_mgr = get_roi_manager()
            
            if not new_url:
                return {"status": "error", "message": "No URL provided"}
            
            detector = get_detector()
            if detector:
                detector.stop()
                time.sleep(2)
                gc.collect()
            
            current_camera_url = new_url
            
            # Создаем новый детектор с roi_manager
            detector = MotionDetector(
                motion_threshold=200, 
                min_area=5, 
                rtsp_url=new_url,
                has_audio=has_audio,
                camera_name=camera_name,
                roi_manager=roi_mgr
            )
            detector.start()
            
            time.sleep(2)
            
            logger.info(f"Switched to camera: {camera_name} ({new_url}) [Audio: {has_audio}]")
            return {"status": "ok", "message": f"Switched to {camera_name}"}
            
        except Exception as e:
            logger.error(f"Error switching camera: {e}")
            return {"status": "error", "message": str(e)}
    
    @app.post("/toggle_recording")
    async def toggle_recording(request: Request):
        try:
            data = await request.json()
            new_state = data.get('enabled', True)
            detector = get_detector()
            
            if not new_state and config.recording_enable:
                if detector and hasattr(detector, 'video_recorder'):
                    if detector.video_recorder.recording:
                        logger.info("Stopping current recording due to disable...")
                        detector.video_recorder.stop_recording()
            
            config.recording_enable = new_state
            status = "ON" if config.recording_enable else "OFF"
            logger.info(f"Recording toggled: {status}")
            return {"status": "ok", "recording_enabled": config.recording_enable}
        except Exception as e:
            logger.error(f"Error toggling recording: {e}")
            return {"status": "error", "message": str(e)}
    
    @app.post("/toggle_detection")
    async def toggle_detection(request: Request):
        try:
            data = await request.json()
            new_state = data.get('enabled', True)
            config.detection_enabled = new_state
            status = "ON" if config.detection_enabled else "OFF"
            logger.info(f"Detection toggled: {status}")
            return {"status": "ok", "detection_enabled": config.detection_enabled}
        except Exception as e:
            logger.error(f"Error toggling detection: {e}")
            return {"status": "error", "message": str(e)}
    
    @app.get("/motion_status")
    async def motion_status():
        detector = get_detector()
        if detector:
            return detector.get_motion_status()
        return {"error": "Detector not available"}
    
    # ===== ROI API Endpoints =====
    
    @app.get("/roi/{camera_name}")
    async def get_roi(camera_name: str):
        roi_mgr = get_roi_manager()
        if not roi_mgr:
            return {"status": "error", "message": "ROI Manager not available"}
        try:
            roi = roi_mgr.get_roi(camera_name)
            return {"status": "ok", "camera_name": camera_name, "roi": roi}
        except Exception as e:
            logger.error(f"Error getting ROI: {e}")
            return {"status": "error", "message": str(e)}
    
    @app.post("/roi/set")
    async def set_roi(request: CameraROIRequest):
        roi_mgr = get_roi_manager()
        if not roi_mgr:
            return {"status": "error", "message": "ROI Manager not available"}
        try:
            roi_dict = request.roi.dict()
            roi_mgr.set_roi(request.camera_name, roi_dict)
            return {
                "status": "ok", 
                "message": f"ROI set for {request.camera_name}",
                "camera_name": request.camera_name,
                "roi": roi_dict
            }
        except Exception as e:
            logger.error(f"Error setting ROI: {e}")
            return {"status": "error", "message": str(e)}
    
    @app.post("/roi/reset/{camera_name}")
    async def reset_roi(camera_name: str):
        roi_mgr = get_roi_manager()
        if not roi_mgr:
            return {"status": "error", "message": "ROI Manager not available"}
        try:
            roi_mgr.reset_roi(camera_name)
            return {
                "status": "ok",
                "message": f"ROI reset for {camera_name}",
                "camera_name": camera_name
            }
        except Exception as e:
            logger.error(f"Error resetting ROI: {e}")
            return {"status": "error", "message": str(e)}
    
    @app.get("/roi/all")
    async def get_all_rois():
        roi_mgr = get_roi_manager()
        if not roi_mgr:
            return {"status": "error", "message": "ROI Manager not available"}
        try:
            return {"status": "ok", "rois": roi_mgr.rois}
        except Exception as e:
            logger.error(f"Error getting all ROIs: {e}")
            return {"status": "error", "message": str(e)}
    
    @app.get("/recordings")
    async def list_recordings():
        try:
            recordings = []
            pattern = os.path.join(RECORDINGS_DIR, "motion_*.mp4")
            files = glob.glob(pattern)
            files.sort(key=os.path.getctime, reverse=True)
            
            for f in files[:50]:
                recordings.append({
                    "name": os.path.basename(f),
                    "size": os.path.getsize(f),
                    "created": datetime.fromtimestamp(os.path.getctime(f)).isoformat()
                })
            
            return {"recordings": recordings}
        except Exception as e:
            logger.error(f"Error listing recordings: {e}")
            return {"recordings": [], "error": str(e)}
    
    @app.get("/health")
    async def health():
        detector = get_detector()
        try:
            status = {
                "status": "running",
                "detector": detector is not None and detector.running,
                "recording_enabled": config.recording_enable,
                "detection_enabled": config.detection_enabled,
                "recordings_count": len(glob.glob(os.path.join(RECORDINGS_DIR, "motion_*.mp4"))),
            }
            if detector:
                status["motion_detected"] = detector.is_motion_detected
                status["has_audio"] = detector.has_audio
                status["camera_name"] = detector.camera_name
            return status
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return {"status": "error", "message": str(e)}