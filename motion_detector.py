import cv2
import numpy as np
import time
import threading
import json
import queue
import gc
import os

from config import (
    DEFAULT_CAMERA, DISPLAY_HEIGHT, DISPLAY_WIDTH, RECORDINGS_DIR, logger, config
)
from roi_manager import ROIManager
from video_recorder import VideoRecorder
from audio_streamer import AudioStreamer

class MotionDetector:
    def __init__(self, motion_threshold, min_area, rtsp_url, has_audio=True, camera_name="", roi_manager: ROIManager=None, show_roi_in_right_panel=True):
        self.rtsp_url = rtsp_url
        self.motion_threshold = motion_threshold
        self.min_area = min_area
        self.has_audio = has_audio
        self.camera_name = camera_name or DEFAULT_CAMERA
        self.roi_manager = roi_manager
        self.show_roi_in_right_panel = show_roi_in_right_panel
        self.cap = None
        self.cap_lock = threading.Lock()
        self._init_capture()
        
        self.mog2 = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=70, detectShadows=True)
        self.frame_skip = 10
        self.frame_count = 0
        self.target_fps = 5
        self.current_frame = None
        self.running = True
        self.last_update = time.time()
        
        self.lock = threading.Lock()
        self.frame_processing = False
        self.thread = None
        self.stopped = False
        
        self.total_motion_area = 0
        self.is_motion_detected = False
        self.motion_cooldown = 0
        self.cooldown_frames = 3
        
        # Only create AudioStreamer if audio is enabled
        self.audio_streamer = AudioStreamer(rtsp_url) if self.has_audio else None
        
        self.video_recorder = VideoRecorder(rtsp_url, RECORDINGS_DIR)
        
        # SSE clients
        self.sse_clients = []
        self.sse_lock = threading.Lock()
        self.sse_running = True
        
        # Start status broadcaster
        self.status_thread = threading.Thread(target=self._broadcast_status)
        self.status_thread.daemon = True
        self.status_thread.start()
        
        # Counter for reconnection attempts
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.last_reconnect_time = 0
    
    def has_audio_available(self) -> bool:
        """Check if audio is available"""
        return self.audio_streamer is not None and self.audio_streamer.enable_audio
    
    def set_show_roi_in_right_panel(self, enabled):
        """Toggle between showing fg_mask and ROI area in the right panel"""
        self.show_roi_in_right_panel = enabled
            
    def _init_capture(self):
        """Initialize video capture with retry logic"""
        with self.cap_lock:
            if self.cap is not None:
                try:
                    self.cap.release()
                except:
                    pass
                self.cap = None
            
            print("📷 Initializing VideoCapture...")
            max_attempts = 5
            for attempt in range(max_attempts):
                try:
                    self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
                    
                    # Set properties to prevent timeout
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    self.cap.set(cv2.CAP_PROP_FPS, 10)
                    
                    if self.cap.isOpened():
                        # Test read
                        ret, frame = self.cap.read()
                        if ret and frame is not None and frame.size > 0:
                            print("✅ VideoCapture ready")
                            self.reconnect_attempts = 0
                            return True
                    
                    # If we get here, open failed or read failed
                    self.cap.release()
                    self.cap = None
                    print(f"⚠️ Attempt {attempt + 1}/{max_attempts} failed, retrying...")
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error initializing capture (attempt {attempt + 1}): {e}")
                    if self.cap:
                        try:
                            self.cap.release()
                        except:
                            pass
                        self.cap = None
                    time.sleep(1)
            
            print("❌ Failed to initialize VideoCapture after all attempts")
            return False
    
    def _broadcast_status(self):
        last_status = None
        while self.sse_running and self.running and not config.shutdown_flag:
            try:
                status = self.get_motion_status()
                if status != last_status:
                    data = json.dumps(status)
                    with self.sse_lock:
                        disconnected = []
                        for client_queue in self.sse_clients:
                            try:
                                client_queue.put_nowait(data)
                            except queue.Full:
                                disconnected.append(client_queue)
                            except Exception:
                                disconnected.append(client_queue)
                        # Remove disconnected clients
                        for client in disconnected:
                            if client in self.sse_clients:
                                try:
                                    self.sse_clients.remove(client)
                                except ValueError:
                                    pass
                    last_status = status.copy() if status else None
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"SSE broadcast error: {e}")
                time.sleep(0.5)
    
    def add_sse_client(self, queue):
        with self.sse_lock:
            self.sse_clients.append(queue)
    
    def remove_sse_client(self, queue):
        with self.sse_lock:
            if queue in self.sse_clients:
                try:
                    self.sse_clients.remove(queue)
                except ValueError:
                    pass
    
    def update_params(self, motion_threshold=None, min_area=None):
        if motion_threshold is not None:
            self.motion_threshold = motion_threshold
        if min_area is not None:
            self.min_area = min_area
    
    def get_motion_status(self):
        return {
            'motion_detected': self.is_motion_detected,
            'motion_area': self.total_motion_area,
            'threshold': self.motion_threshold,
            'min_area': self.min_area,
            'recording': self.video_recorder.recording if self.video_recorder else False,
            'recording_enabled': config.recording_enable,
            'detection_enabled': config.detection_enabled,
            'has_audio': self.has_audio and self.audio_streamer is not None,
            'camera_name': self.camera_name,
            'roi': self.roi_manager.get_roi(self.camera_name) if self.roi_manager else None
        }
    
    def restart_capture(self):
        print("🔄 Restarting video capture...")
        self._init_capture()
        if self.cap is not None and self.cap.isOpened():
            print("✅ Video capture restarted")
        else:
            print("⚠️ Failed to restart video capture")
    
    def _create_right_panel(self, frame_resized, fg_mask):
        """Create the right panel based on show_roi_in_right_panel setting"""
        
        if self.show_roi_in_right_panel:
            # Show ROI area scaled (zoom in on ROI)
            roi = self.roi_manager.get_roi(self.camera_name)
            if roi['enabled']:
                height, width = frame_resized.shape[:2]
                x = int(roi['x'] * width)
                y = int(roi['y'] * height)
                roi_width = int(roi['width'] * width)
                roi_height = int(roi['height'] * height)
                
                # Extract ROI from the original frame
                roi_area = frame_resized[y:y+roi_height, x:x+roi_width]
                
                # Scale ROI to fill the right panel
                if roi_area.size > 0:
                    if not self.is_motion_detected:
                        roi_area = cv2.convertScaleAbs(roi_area, alpha=0.3, beta=0)
                    
                    right_panel = cv2.resize(roi_area, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
                    
                    # Add ROI indicator
                    cv2.putText(right_panel, "ROI AREA (ZOOMED)", 
                               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    
                    # Add ROI info
                    cv2.putText(right_panel, f"Position: ({roi['x']:.2f}, {roi['y']:.2f})", 
                               (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                    cv2.putText(right_panel, f"Size: {roi['width']:.2f}x{roi['height']:.2f}", 
                               (10, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                    
                    return right_panel
                else:
                    # Fallback if ROI extraction fails
                    placeholder = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 3), dtype=np.uint8)
                    cv2.putText(placeholder, "ROI AREA", 
                               (200, 250), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (100, 100, 100), 3)
                    cv2.putText(placeholder, "EMPTY OR INVALID", 
                               (150, 300), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (100, 100, 100), 2)
                    return placeholder
            else:
                # ROI is disabled
                placeholder = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 3), dtype=np.uint8)
                cv2.putText(placeholder, "ROI AREA", 
                           (200, 250), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (100, 100, 100), 3)
                cv2.putText(placeholder, "ROI DISABLED", 
                           (150, 300), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (100, 100, 100), 2)
                cv2.putText(placeholder, "Enable ROI in settings", 
                           (150, 340), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 80, 80), 2)
                return placeholder
        else:
            # Show the original fg_mask
            fg_mask_colored = cv2.cvtColor(fg_mask, cv2.COLOR_GRAY2BGR)
            right_panel = cv2.resize(fg_mask_colored, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
            
            # Add label
            cv2.putText(right_panel, "MOTION MASK", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            return right_panel
    
    def process_frame(self):
        detection_was_disabled = True
        frame_timeout_counter = 0
        MAX_TIMEOUTS = 5
        reconnect_delay = 1
        
        while self.running and not config.shutdown_flag:
            try:
                with self.lock:
                    if not self.running or config.shutdown_flag:
                        break
                    self.frame_processing = True
                
                if config.detection_enabled and detection_was_disabled:
                    self._init_capture()
                    detection_was_disabled = False
                    print("🎯 Detection restarted - capture reinitialized")
                
                if not config.detection_enabled:
                    detection_was_disabled = True
                    placeholder = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 3), dtype=np.uint8)
                    cv2.putText(placeholder, "MOTION DETECTION", 
                                (150, 220), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (100, 100, 100), 3)
                    cv2.putText(placeholder, "DISABLED", 
                                (220, 270), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (100, 100, 100), 3)
                    cv2.putText(placeholder, "Click 'Start Detection' to enable", 
                                (150, 320), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 80, 80), 2)
                    
                    mask_placeholder = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 3), dtype=np.uint8)
                    full_screen_frame = np.hstack((placeholder, mask_placeholder))
                    
                    status_bar = np.zeros((40, full_screen_frame.shape[1], 3), dtype=np.uint8)
                    status_bar[:, :] = (40, 40, 40)
                    cv2.putText(status_bar, "⏸️ DETECTION PAUSED", 
                                (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 2)
                    
                    full_screen_frame = np.vstack((status_bar, full_screen_frame))
                    self.current_frame = full_screen_frame
                    
                    time.sleep(0.5)
                    with self.lock:
                        self.frame_processing = False
                    continue
                
                # Check if capture is available
                with self.cap_lock:
                    if self.cap is None or not self.cap.isOpened():
                        print("⚠️ Video capture not available, reinitializing...")
                        self._init_capture()
                        if self.cap is None or not self.cap.isOpened():
                            time.sleep(reconnect_delay)
                            with self.lock:
                                self.frame_processing = False
                            continue
                
                # Read frame with timeout handling
                ret = False
                frame = None
                try:
                    with self.cap_lock:
                        ret, frame = self.cap.read()
                except Exception as e:
                    logger.error(f"Error reading frame: {e}")
                    ret = False
                
                # Check if frame read failed or is empty
                if not ret or frame is None:
                    frame_timeout_counter += 1
                    if frame_timeout_counter >= MAX_TIMEOUTS:
                        logger.warning("⚠️ Multiple frame read failures, reinitializing...")
                        self._init_capture()
                        frame_timeout_counter = 0
                    with self.lock:
                        self.frame_processing = False
                    time.sleep(reconnect_delay)
                    continue
                else:
                    frame_timeout_counter = 0  # Reset counter on success
                
                # Check if frame is valid (not empty)
                if frame.size == 0:
                    print("⚠️ Empty frame received, skipping...")
                    with self.lock:
                        self.frame_processing = False
                    time.sleep(0.1)
                    continue
                
                self.frame_count += 1
                if self.frame_count % self.frame_skip != 0:
                    with self.lock:
                        self.frame_processing = False
                    continue
                
                try:
                    frame_resized = cv2.resize(frame, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
                    
                    # Apply ROI
                    roi_frame = self.roi_manager.apply_roi_to_frame(frame_resized, self.camera_name)
                    
                    # Convert to grayscale for motion detection
                    frame_gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
                    
                    fg_mask = self.mog2.apply(frame_gray)
                    fg_mask = cv2.medianBlur(fg_mask, 5)
                    
                    # Only detect motion within ROI
                    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    
                    self.total_motion_area = 0
                    frame_with_boxes = frame_resized.copy()
                    
                    for contour in contours:
                        area = cv2.contourArea(contour)
                        if area > self.min_area:
                            self.total_motion_area += area
                            x, y, w, h = cv2.boundingRect(contour)
                            cv2.rectangle(frame_with_boxes, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    
                    if self.total_motion_area > self.motion_threshold:
                        self.is_motion_detected = True
                        self.motion_cooldown = self.cooldown_frames
                    elif self.motion_cooldown > 0:
                        self.motion_cooldown -= 1
                    else:
                        self.is_motion_detected = False
                    
                    current_time = time.time()
                    self.video_recorder.process_motion(self.is_motion_detected, frame_resized, current_time)
                    
                    if self.is_motion_detected:
                        display_frame = frame_with_boxes.copy()
                        cv2.putText(display_frame, f"MOTION DETECTED! Area: {self.total_motion_area:.0f}", 
                                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                        cv2.putText(display_frame, f"Threshold: {self.motion_threshold}", 
                                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                        cv2.putText(display_frame, f"Min Area: {self.min_area}", 
                                    (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                        if self.video_recorder.recording:
                            cv2.putText(display_frame, "🔴 RECORDING", 
                                        (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    else:
                        display_frame = frame_resized.copy()
                        display_frame = cv2.convertScaleAbs(display_frame, alpha=0.3, beta=0)
                        cv2.putText(display_frame, "NO MOTION DETECTED", 
                                    (120, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (100, 100, 100), 3)
                        cv2.putText(display_frame, f"Motion Area: {self.total_motion_area:.0f}", 
                                    (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 80, 80), 2)
                        cv2.putText(display_frame, f"Threshold: {self.motion_threshold}", 
                                    (200, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 80, 80), 2)
                        cv2.putText(display_frame, f"Min Area: {self.min_area}", 
                                    (200, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 80, 80), 2)
                        if self.video_recorder.recording:
                            cv2.putText(display_frame, "🔴 RECORDING", 
                                        (200, 330), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    
                    # Show ROI on display frame
                    roi = self.roi_manager.get_roi(self.camera_name)
                    if roi['enabled']:
                        height, width = display_frame.shape[:2]
                        x = int(roi['x'] * width)
                        y = int(roi['y'] * height)
                        roi_width = int(roi['width'] * width)
                        roi_height = int(roi['height'] * height)
                        cv2.rectangle(display_frame, (x, y), (x+roi_width, y+roi_height), (0, 255, 255), 2)
                        cv2.putText(display_frame, "ROI", (x+5, y+25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                    
                    # Create the right panel based on the setting
                    right_panel = self._create_right_panel(frame_resized, fg_mask)
                    
                    # Combine left and right panels
                    full_screen_frame = np.hstack((display_frame, right_panel))
                    self.current_frame = full_screen_frame
                    
                    elapsed = time.time() - self.last_update
                    if elapsed < 1/self.target_fps:
                        time.sleep(1/self.target_fps - elapsed)
                    self.last_update = time.time()
                    
                except Exception as e:
                    logger.error(f"Error processing frame: {e}")
                    # Don't break, continue to next frame
                    continue
                
            except Exception as e:
                logger.error(f"Critical error in process_frame: {e}")
                time.sleep(1)  # Wait before retrying
            finally:
                with self.lock:
                    self.frame_processing = False
        
        self.stopped = True
        print("Frame processing thread stopped")
    
    def start(self):
        self.thread = threading.Thread(target=self.process_frame)
        self.thread.daemon = True
        self.thread.start()
    
    def get_jpeg(self):
        try:
            if self.current_frame is None:
                return None
            _, jpeg = cv2.imencode('.jpg', self.current_frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
            return jpeg.tobytes()
        except Exception as e:
            logger.error(f"Error encoding JPEG: {e}")
            return None
    
    def stop(self):
        if self.stopped:
            return
        self.sse_running = False
        self.running = False
        
        # Clear SSE clients
        with self.sse_lock:
            for q in self.sse_clients:
                try:
                    q.put_nowait('{"type":"shutdown"}')
                except:
                    pass
            self.sse_clients.clear()
        
        # Stop video recorder
        if self.video_recorder:
            try:
                self.video_recorder.stop()
            except:
                pass
        
        # Stop audio streamer only if it exists
        if self.audio_streamer:
            try:
                self.audio_streamer.cleanup()
            except:
                pass
        
        # Release camera with proper error handling
        with self.cap_lock:
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception as e:
                    logger.error(f"Error releasing camera: {e}")
                finally:
                    self.cap = None
        
        # Wait a moment for resources to free
        time.sleep(0.5)
        
        # Force garbage collection
        gc.collect()
        
        self.stopped = True
        print("MotionDetector stopped")