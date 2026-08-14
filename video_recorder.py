import os
import threading
import time
import cv2
import glob
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
import numpy as np

from config import (
    RECORDINGS_DIR, RECORD_BUFFER_SECONDS, RECORD_AFTER_SECONDS,
    MIN_RECORD_SECONDS, MAX_RECORD_SECONDS, logger, config
)


class VideoRecorder:
    def __init__(self, rtsp_url: str, output_dir: str = RECORDINGS_DIR) -> None:
        self.rtsp_url: str = rtsp_url
        self.output_dir: str = output_dir
        self.recording: bool = False
        self.recording_start_time: float = 0
        self.buffer: List[Tuple[float, np.ndarray]] = []
        self.buffer_size: int = int(RECORD_BUFFER_SECONDS * 10)
        self.recording_thread: Optional[threading.Thread] = None
        self.running: bool = True
        self.motion_history: List[bool] = []
        self.recording_frames: List[np.ndarray] = []
        self.writer: Optional[cv2.VideoWriter] = None
        self.current_filepath: Optional[str] = None
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        self._clean_old_recordings(keep=100)
        print(f"📹 VideoRecorder initialized, saving to: {output_dir}")
    
    def _clean_old_recordings(self, keep: int = 100) -> None:
        pattern: str = os.path.join(self.output_dir, "motion_*.mp4")
        files: List[str] = glob.glob(pattern)
        if len(files) > keep:
            files.sort(key=os.path.getctime)
            for f in files[:-keep]:
                try:
                    os.remove(f)
                    print(f"🧹 Removed old recording: {os.path.basename(f)}")
                except:
                    pass
    
    def add_frame(self, frame: Optional[np.ndarray], timestamp: float) -> None:
        if not self.running:
            return
        try:
            if frame is not None and frame.size > 0:
                self.buffer.append((timestamp, frame.copy()))
                if len(self.buffer) > self.buffer_size:
                    self.buffer.pop(0)
        except Exception as e:
            logger.error(f"Error adding frame to buffer: {e}")
    
    def start_recording(self) -> None:
        if self.recording:
            return
        
        try:
            timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_filepath = os.path.join(self.output_dir, f"motion_{timestamp}.mp4")
            
            if not self.buffer:
                print("⚠️ No buffer frames available to start recording")
                return
            
            self.recording_frames = []
            for _, frame in self.buffer:
                if frame is not None and frame.size > 0:
                    self.recording_frames.append(frame.copy())
            
            self.recording = True
            self.recording_start_time = time.time()
            self.motion_history = []
            print(f"🔴 RECORDING STARTED: {os.path.basename(self.current_filepath)}")
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            self.recording = False
    
    def stop_recording(self) -> None:
        if not self.recording:
            return
        
        # Check if filepath is set
        if self.current_filepath is None:
            print("❌ No filepath set for recording")
            self.recording = False
            return
        
        try:
            duration: float = time.time() - self.recording_start_time
            
            # Filter out invalid frames
            valid_frames: List[np.ndarray] = []
            for frame in self.recording_frames:
                if frame is not None and frame.size > 0 and frame.shape[0] > 0 and frame.shape[1] > 0:
                    valid_frames.append(frame)
            
            if len(valid_frames) < MIN_RECORD_SECONDS * 10:
                print(f"⏭️ Recording too short ({len(valid_frames)} valid frames), discarding")
                self.recording_frames = []
                self.recording = False
                return
            
            first_frame: np.ndarray = valid_frames[0]
            height: int = first_frame.shape[0]
            width: int = first_frame.shape[1]
            
            # Validate dimensions
            if height == 0 or width == 0:
                print("❌ Invalid frame dimensions, discarding recording")
                self.recording_frames = []
                self.recording = False
                return
            
            fourcc: int = cv2.VideoWriter_fourcc(*'mp4v')
            writer: cv2.VideoWriter = cv2.VideoWriter(
                self.current_filepath, fourcc, 10.0, (width, height)
            )
            
            frames_written: int = 0
            for frame in valid_frames:
                writer.write(frame)
                frames_written += 1
            
            writer.release()
            
            # Now current_filepath is definitely not None here
            if os.path.getsize(self.current_filepath) > 0:
                print(f"✅ RECORDING SAVED: {os.path.basename(self.current_filepath)} ({duration:.1f}s, {frames_written} frames)")
                self._clean_old_recordings(keep=100)
            else:
                print(f"❌ Failed to save recording: file is empty")
                try:
                    os.remove(self.current_filepath)
                except:
                    pass
        except Exception as e:
            logger.error(f"Error saving recording: {e}")
            if self.current_filepath and os.path.exists(self.current_filepath):
                try:
                    os.remove(self.current_filepath)
                except:
                    pass
        
        self.recording_frames = []
        self.recording = False
    
    def process_motion(self, is_motion: bool, frame: Optional[np.ndarray], timestamp: float) -> None:
        if not self.running or not config.recording_enable:
            return
        
        try:
            self.add_frame(frame, timestamp)
            
            self.motion_history.append(is_motion)
            if len(self.motion_history) > 10:
                self.motion_history.pop(0)
            
            if is_motion and not self.recording:
                self.start_recording()
            
            if self.recording:
                if frame is not None and frame.size > 0:
                    self.recording_frames.append(frame.copy())
                
                if not is_motion:
                    motion_recent: bool = any(self.motion_history[-5:])
                    if not motion_recent:
                        duration: float = time.time() - self.recording_start_time
                        if duration >= RECORD_AFTER_SECONDS or duration >= MAX_RECORD_SECONDS:
                            self.stop_recording()
                else:
                    duration = time.time() - self.recording_start_time
                    if duration >= MAX_RECORD_SECONDS:
                        self.stop_recording()
        except Exception as e:
            logger.error(f"Error in process_motion: {e}")
    
    def stop(self) -> None:
        self.running = False
        if self.recording:
            self.stop_recording()
        self.buffer.clear()
        self.recording_frames = []