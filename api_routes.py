import os
import time
import glob
import asyncio
import queue
import gc
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

from config import (
    CAMERAS, DEFAULT_CAMERA, RECORDINGS_DIR, logger, config
)
from html_template import HTML_TEMPLATE
from models import CameraROIRequest
from motion_detector import MotionDetector
from roi_manager import ROIManager
from app_state import AppState


def setup_routes(app: FastAPI, state: AppState):
    """
    Setup all API routes with dependency injection
    
    Args:
        app: FastAPI application
        state: Application state container
    """
        
    @app.get("/")
    async def index():
        """Serve the main HTML page"""
        return HTMLResponse(content=open("static/index.html", "r").read())

    @app.get("/api/cameras")
    async def get_cameras():
        """API endpoint to get camera configuration"""
        cameras = {}
        for name, config in CAMERAS.items():
            cameras[name] = {
                "url": config["url"],
                "has_audio": config.get("has_audio", True),
                "is_default": name == DEFAULT_CAMERA
            }
        
        return JSONResponse({
            "status": "ok",
            "selected": next(item for item in CAMERAS if CAMERAS[item]["url"] == state.current_camera_url),
            "cameras": cameras,
            "default_camera": DEFAULT_CAMERA,
            "total": len(cameras)
        })

    @app.get("/stream.mjpg")
    async def stream_mjpeg(request: Request):
        """MJPEG video stream"""
        detector = state.get_detector()
        threshold = request.query_params.get('threshold', 200)
        min_area = request.query_params.get('min_area', 5)
        
        if detector:
            detector.update_params(int(threshold), int(min_area))
        
        async def generate():
            while detector and detector.running:
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
                    logger.error(f"MJPEG stream error: {e}")
                    break
            else:
                print("detector END")                
        
        return StreamingResponse(
            generate(),
            media_type="multipart/x-mixed-replace; boundary=frame"
        )
    
    @app.get("/events")
    async def sse_events():
        """Server-Sent Events endpoint for real-time status updates"""
        detector = state.get_detector()
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
        """Audio stream endpoint"""
        detector = state.get_detector()
        
        if not detector:
            return JSONResponse(
                {"error": "Detector not available"}, 
                status_code=503
            )
        
        # Use the helper method or check directly
        if not detector.has_audio_available():
            return JSONResponse(
                {"error": "Audio not available"}, 
                status_code=404
            )
        
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
        """Switch camera - rewrites the detector instance"""
        try:
            data = await request.json()
            new_url = data.get('url')
            camera_name = data.get('name', 'Unknown')
            has_audio = data.get('has_audio', True)
            
            if not new_url:
                return JSONResponse(
                    {"status": "error", "message": "No URL provided"},
                    status_code=400
                )
            
            # Get current detector
            current_detector = state.get_detector()
            
            # Stop old detector
            if current_detector:
                current_detector.stop()
                await asyncio.sleep(0.5)
                # Let GC happen naturally, or use less aggressive collection
                gc.collect(1)
            
            # Create NEW detector instance
            new_detector = MotionDetector(
                motion_threshold=200,
                min_area=5,
                rtsp_url=new_url,
                has_audio=has_audio,
                camera_name=camera_name,
                roi_manager=state.get_roi_manager()
            )
            new_detector.start()
            
            # Update state with new detector
            state.set_detector(new_detector)
            state.current_camera_url = new_url
            
            await asyncio.sleep(0.5)
            
            logger.info(f"✅ Switched to camera: {camera_name} ({new_url})")
            return JSONResponse({
                "status": "ok", 
                "message": f"Switched to {camera_name}",
                "camera": {
                    "name": camera_name,
                    "url": new_url,
                    "has_audio": has_audio
                }
            })
            
        except Exception as e:
            logger.error(f"Error switching camera: {e}")
            return JSONResponse(
                {"status": "error", "message": str(e)},
                status_code=500
            )
    
    @app.post("/toggle_recording")
    async def toggle_recording(request: Request):
        """Toggle recording on/off"""
        try:
            data = await request.json()
            new_state = data.get('enabled', True)
            detector = state.get_detector()
            
            if not new_state and config.recording_enable:
                if detector and hasattr(detector, 'video_recorder'):
                    if detector.video_recorder.recording:
                        logger.info("Stopping recording...")
                        detector.video_recorder.stop_recording()
            
            config.recording_enable = new_state
            logger.info(f"Recording toggled: {'ON' if new_state else 'OFF'}")
            return JSONResponse({
                "status": "ok", 
                "recording_enabled": config.recording_enable
            })
        except Exception as e:
            logger.error(f"Error toggling recording: {e}")
            return JSONResponse(
                {"status": "error", "message": str(e)},
                status_code=500
            )
    
    @app.post("/toggle_detection")
    async def toggle_detection(request: Request):
        """Toggle motion detection on/off"""
        try:
            data = await request.json()
            new_state = data.get('enabled', True)
            config.detection_enabled = new_state
            logger.info(f"Detection toggled: {'ON' if new_state else 'OFF'}")
            return JSONResponse({
                "status": "ok", 
                "detection_enabled": config.detection_enabled
            })
        except Exception as e:
            logger.error(f"Error toggling detection: {e}")
            return JSONResponse(
                {"status": "error", "message": str(e)},
                status_code=500
            )
    
    @app.get("/motion_status")
    async def motion_status():
        """Get current motion detection status"""
        detector = state.get_detector()
        if detector:
            return detector.get_motion_status()
        return JSONResponse(
            {"error": "Detector not available"},
            status_code=503
        )
    
    # ===== ROI API Endpoints =====
    
    @app.get("/roi/{camera_name}")
    async def get_roi(camera_name: str):
        """Get ROI for specific camera"""
        roi_mgr = state.get_roi_manager()
        if not roi_mgr:
            return JSONResponse(
                {"status": "error", "message": "ROI Manager not available"},
                status_code=503
            )
        try:
            roi = roi_mgr.get_roi(camera_name)
            return JSONResponse({
                "status": "ok", 
                "camera_name": camera_name, 
                "roi": roi
            })
        except Exception as e:
            logger.error(f"Error getting ROI: {e}")
            return JSONResponse(
                {"status": "error", "message": str(e)},
                status_code=500
            )
    
    @app.post("/roi/set")
    async def set_roi(request: CameraROIRequest):
        """Set ROI for specific camera"""
        roi_mgr = state.get_roi_manager()
        if not roi_mgr:
            return JSONResponse(
                {"status": "error", "message": "ROI Manager not available"},
                status_code=503
            )
        try:
            roi_dict = request.roi.dict()
            roi_mgr.set_roi(request.camera_name, roi_dict)
            return JSONResponse({
                "status": "ok",
                "message": f"ROI set for {request.camera_name}",
                "camera_name": request.camera_name,
                "roi": roi_dict
            })
        except Exception as e:
            logger.error(f"Error setting ROI: {e}")
            return JSONResponse(
                {"status": "error", "message": str(e)},
                status_code=500
            )
    
    @app.post("/roi/reset/{camera_name}")
    async def reset_roi(camera_name: str):
        """Reset ROI for specific camera"""
        roi_mgr = state.get_roi_manager()
        if not roi_mgr:
            return JSONResponse(
                {"status": "error", "message": "ROI Manager not available"},
                status_code=503
            )
        try:
            roi_mgr.reset_roi(camera_name)
            return JSONResponse({
                "status": "ok",
                "message": f"ROI reset for {camera_name}",
                "camera_name": camera_name
            })
        except Exception as e:
            logger.error(f"Error resetting ROI: {e}")
            return JSONResponse(
                {"status": "error", "message": str(e)},
                status_code=500
            )
    
    @app.get("/roi/all")
    async def get_all_rois():
        """Get all ROIs"""
        roi_mgr = state.get_roi_manager()
        if not roi_mgr:
            return JSONResponse(
                {"status": "error", "message": "ROI Manager not available"},
                status_code=503
            )
        try:
            return JSONResponse({
                "status": "ok", 
                "rois": roi_mgr.rois
            })
        except Exception as e:
            logger.error(f"Error getting all ROIs: {e}")
            return JSONResponse(
                {"status": "error", "message": str(e)},
                status_code=500
            )