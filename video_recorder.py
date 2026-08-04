import os
import time
import cv2
import glob
import logging
from datetime import datetime
from typing import List, Tuple, Optional
import numpy as np

from config import (
    RECORDINGS_DIR, RECORD_BUFFER_SECONDS, RECORD_AFTER_SECONDS,
    MIN_RECORD_SECONDS, MAX_RECORD_SECONDS, logger, config
)

class VideoRecorder:
    def __init__(self, rtsp_url, output_dir=RECORDINGS_DIR):
        self.rtsp_url = rtsp_url
        self.output_dir = output_dir
        self.recording = False
        self.recording_start_time = 0
        self.buffer = []
        self.buffer_size = int(RECORD_BUFFER_SECONDS * 10)
        self.recording_thread = None
        self.running = True
        self.motion_history = []
        self.last_save_path = None
        self.recording_frames = []
        self.writer = None
        self.current_filepath = None
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        self._clean_old_recordings(keep=100)
        print(f"📹 VideoRecorder initialized, saving to: {output_dir}")
    
    def _clean_old_recordings(self, keep=100):
        pattern = os.path.join(self.output_dir, "motion_*.mp4")
        files = glob.glob(pattern)
        if len(files) > keep:
            files.sort(key=os.path.getctime)
            for f in files[:-keep]:
                try:
                    os.remove(f)
                    print(f"🧹 Removed old recording: {os.path.basename(f)}")
                except:
                    pass
    
    def add_frame(self, frame, timestamp):
        if not self.running:
            return
        try:
            if frame is not None and frame.size > 0:
                self.buffer.append((timestamp, frame.copy()))
                if len(self.buffer) > self.buffer_size:
                    self.buffer.pop(0)
        except Exception as e:
            logger.error(f"Error adding frame to buffer: {e}")
    
    def start_recording(self):
        if self.recording:
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
    
    def stop_recording(self):
        if not self.recording:
            return
        
        try:
            duration = time.time() - self.recording_start_time
            
            # Filter out invalid frames
            valid_frames = []
            for frame in self.recording_frames:
                if frame is not None and frame.size > 0 and frame.shape[0] > 0 and frame.shape[1] > 0:
                    valid_frames.append(frame)
            
            if len(valid_frames) < MIN_RECORD_SECONDS * 10:
                print(f"⏭️ Recording too short ({len(valid_frames)} valid frames), discarding")
                self.recording_frames = []
                self.recording = False
                return
            
            first_frame = valid_frames[0]
            height, width = first_frame.shape[:2]
            
            # Validate dimensions
            if height == 0 or width == 0:
                print("❌ Invalid frame dimensions, discarding recording")
                self.recording_frames = []
                self.recording = False
                return
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(self.current_filepath, fourcc, 10.0, (width, height))
            
            frames_written = 0
            for frame in valid_frames:
                writer.write(frame)
                frames_written += 1
            
            writer.release()
            
            if os.path.getsize(self.current_filepath) > 0:
                self.last_save_path = self.current_filepath
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
            try:
                if os.path.exists(self.current_filepath):
                    os.remove(self.current_filepath)
            except:
                pass
        
        self.recording_frames = []
        self.recording = False
    
    def process_motion(self, is_motion, frame, timestamp):
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
                    motion_recent = any(self.motion_history[-5:])
                    if not motion_recent:
                        duration = time.time() - self.recording_start_time
                        if duration >= RECORD_AFTER_SECONDS or duration >= MAX_RECORD_SECONDS:
                            self.stop_recording()
                else:
                    duration = time.time() - self.recording_start_time
                    if duration >= MAX_RECORD_SECONDS:
                        self.stop_recording()
        except Exception as e:
            logger.error(f"Error in process_motion: {e}")
    
    def stop(self):
        self.running = False
        if self.recording:
            self.stop_recording()
        self.buffer.clear()
        self.recording_frames = []
    
    def get_last_recording(self):
        return self.last_save_path