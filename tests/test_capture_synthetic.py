from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np

from app.capture import CaptureService
from app.composer import FrameComposer, encode_jpeg
from app.motion import MotionAnalyzer, MotionParams
from app.recorder import Recorder
from app.models import ROISettings


class VideoSource:
    """Plays a list of frames once, then stops returning frames."""
    def __init__(self, frames):
        self.frames = frames
        self.i = 0
        self.lock = threading.Lock()

    def read(self):
        with self.lock:
            if self.i >= len(self.frames):
                return None
            f = self.frames[self.i]
            self.i += 1
            return f

    def close(self):
        pass


def test_full_pipeline_detects_and_records(tmp_path: Path):
    # 20 blank frames, then 10 frames with a bright rectangle (motion), then blanks
    blank = np.zeros((60, 80, 3), dtype=np.uint8)
    motion = blank.copy()
    motion[20:40, 20:50] = 255
    frames = [blank] * 20 + [motion] * 10 + [blank] * 10

    analyzer = MotionAnalyzer(MotionParams(threshold=20, min_area=10))
    composer = FrameComposer(80, 60)
    recorder = Recorder(tmp_path, buffer_seconds=0.2, after_seconds=0.2,
                        min_seconds=0.0, max_seconds=2.0, fps=10, keep=5, size=(80, 60))
    recorder.set_enabled(True)

    detections = []
    jpegs = []

    def on_frame(frame, ts):
        roi = ROISettings()
        result = analyzer.analyze(frame, roi)
        detections.append(result.detected)
        annotated = composer.annotate(result.frame_bgr, result.detected, result.area,
                                      analyzer.params.threshold, analyzer.params.min_area,
                                      roi, recorder.recording)
        jpegs.append(encode_jpeg(annotated))
        recorder.on_frame(annotated, result.detected, time.monotonic())

    cap = CaptureService(lambda: VideoSource(frames), on_frame)
    cap.start()
    # Wait until source is exhausted
    for _ in range(200):
        time.sleep(0.02)
        if not cap.healthy and not cap._thread.is_alive():
            break
    cap.stop()
    recorder.stop()

    assert any(detections), "pipeline should detect motion"
    assert any(j for j in jpegs), "pipeline should produce jpegs"
    assert list(tmp_path.glob("motion_*.mp4")), "recorder should produce a file"
