import asyncio
import queue
import gc
from typing import Dict, Any, Optional, AsyncGenerator, List
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

from config import CAMERAS, DEFAULT_CAMERA, logger, config
from models import CameraROIRequest
from motion_detector import MotionDetector
from app_state import AppState
from roi_manager import ROIManager


def setup_routes(app: FastAPI, state: AppState) -> None:
    """Setup all API routes"""
    
    # Helper to get detector
    def get_detector() -> MotionDetector:
        detector = state.get_detector()
        if not detector:
            raise HTTPException(503, "Detector not available")
        return detector
    
    # Helper to get ROI manager
    def get_roi_manager() -> ROIManager:
        roi_mgr = state.get_roi_manager()
        if not roi_mgr:
            raise HTTPException(503, "ROI Manager not available")
        return roi_mgr
    
    @app.get("/")
    async def index() -> HTMLResponse:
        with open("static/index.html", "r") as f:
            return HTMLResponse(content=f.read())

    @app.get("/api/cameras")
    async def get_cameras() -> JSONResponse:
        cameras = {
            name: {"url": cfg["url"], "has_audio": cfg.get("has_audio", True)}
            for name, cfg in CAMERAS.items()
        }
        
        selected = next(
            (name for name, cfg in CAMERAS.items() if cfg["url"] == state.current_camera_url),
            DEFAULT_CAMERA
        )
        
        return JSONResponse({
            "selected": selected,
            "cameras": cameras,
            "default_camera": DEFAULT_CAMERA,
            "total": len(cameras)
        })

    @app.get("/stream.mjpg")
    async def stream_mjpeg(request: Request) -> StreamingResponse:
        detector = get_detector()
        
        threshold = int(request.query_params.get('threshold', 200))
        min_area = int(request.query_params.get('min_area', 5))
        detector.update_params(threshold, min_area)
        
        async def generate() -> AsyncGenerator[bytes, None]:
            while detector.running:
                try:
                    jpeg = detector.get_jpeg()
                    if jpeg:
                        yield (
                            b'--frame\r\n'
                            b'Content-Type: image/jpeg\r\n'
                            b'Content-Length: ' + str(len(jpeg)).encode() + b'\r\n\r\n'
                            + jpeg + b'\r\n'
                        )
                    await asyncio.sleep(1/15)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"MJPEG error: {e}")
                    break
        
        return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")
    
    @app.get("/events")
    async def sse_events() -> StreamingResponse:
        detector = get_detector()
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=10)
        
        with detector.sse_lock:
            detector.sse_clients.append(q)
        
        async def generate() -> AsyncGenerator[str, None]:
            try:
                while detector.running:
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
                with detector.sse_lock:
                    if q in detector.sse_clients:
                        detector.sse_clients.remove(q)
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
    
    @app.get("/audio.wav", response_class=StreamingResponse)
    async def audio_stream() -> StreamingResponse:
        detector = get_detector()
        
        if detector.audio_streamer is None:
            raise HTTPException(404, "Audio not available")
        
        streamer = detector.audio_streamer
        assert streamer is not None
        audio_queue = streamer.subscribe_client()
        
        async def generate() -> AsyncGenerator[bytes, None]:
            try:
                yield streamer.wav_header
                while detector.running:
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
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
        
    @app.post("/switch_camera")
    async def switch_camera(request: Request) -> JSONResponse:
        try:
            data = await request.json()
            new_url = data.get('url')
            camera_name = data.get('name', 'Unknown')
            has_audio = data.get('has_audio', True)
            
            if not new_url:
                raise HTTPException(400, "No URL provided")
            
            # Stop old detector
            current = state.get_detector()
            if current:
                current.stop()
                await asyncio.sleep(0.5)
                gc.collect(1)
            
            # Create new detector
            new_detector = MotionDetector(
                motion_threshold=200,
                min_area=5,
                rtsp_url=new_url,
                has_audio=has_audio,
                camera_name=camera_name,
                roi_manager=state.get_roi_manager()
            )
            new_detector.start()
            
            state.set_detector(new_detector)
            state.current_camera_url = new_url
            await asyncio.sleep(0.5)
            
            logger.info(f"✅ Switched to camera: {camera_name}")
            return JSONResponse({
                "message": f"Switched to {camera_name}",
                "camera": {"name": camera_name, "url": new_url, "has_audio": has_audio}
            })
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error switching camera: {e}")
            raise HTTPException(500, str(e))
    
    @app.post("/toggle_recording")
    async def toggle_recording(request: Request) -> JSONResponse:
        try:
            data = await request.json()
            new_state = data.get('enabled', True)
            detector = get_detector()
            
            if not new_state and config.recording_enable:
                if detector.video_recorder:
                    logger.info("Stopping recording...")
                    detector.video_recorder.stop_recording()
            
            config.recording_enable = new_state
            logger.info(f"Recording: {'ON' if new_state else 'OFF'}")
            return JSONResponse({"recording_enabled": config.recording_enable})
            
        except Exception as e:
            logger.error(f"Error toggling recording: {e}")
            raise HTTPException(500, str(e))
    
    @app.post("/toggle_detection")
    async def toggle_detection(request: Request) -> JSONResponse:
        try:
            data = await request.json()
            config.detection_enabled = data.get('enabled', True)
            logger.info(f"Detection: {'ON' if config.detection_enabled else 'OFF'}")
            return JSONResponse({"detection_enabled": config.detection_enabled})
            
        except Exception as e:
            logger.error(f"Error toggling detection: {e}")
            raise HTTPException(500, str(e))
    
    @app.get("/motion_status")
    async def motion_status() -> JSONResponse:
        try:
            return get_detector().get_motion_status()
        except HTTPException:
            return JSONResponse({"error": "Detector not available"}, status_code=503)
    
    # ===== ROI Endpoints =====
    
    @app.get("/roi/{camera_name}")
    async def get_roi(camera_name: str) -> JSONResponse:
        try:
            roi = get_roi_manager().get_roi(camera_name)
            return JSONResponse({"camera_name": camera_name, "roi": roi.model_dump()})
        except Exception as e:
            logger.error(f"Error getting ROI: {e}")
            raise HTTPException(500, str(e))
    
    @app.post("/roi/set")
    async def set_roi(request: CameraROIRequest) -> JSONResponse:
        try:
            get_roi_manager().set_roi(request.camera_name, request.roi)
            return JSONResponse({
                "message": f"ROI set for {request.camera_name}",
                "camera_name": request.camera_name,
                "roi": request.roi.model_dump()
            })
        except Exception as e:
            logger.error(f"Error setting ROI: {e}")
            raise HTTPException(500, str(e))
    
    @app.post("/roi/reset/{camera_name}")
    async def reset_roi(camera_name: str) -> JSONResponse:
        try:
            get_roi_manager().reset_roi(camera_name)
            return JSONResponse({
                "message": f"ROI reset for {camera_name}",
                "camera_name": camera_name
            })
        except Exception as e:
            logger.error(f"Error resetting ROI: {e}")
            raise HTTPException(500, str(e))