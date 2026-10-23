from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

import numpy as np
from numpy.typing import NDArray

from app.audio import AudioService
from app.capture import CaptureService, FrameSource, OpenCVSource
from app.composer import FrameComposer, encode_jpeg
from app.events import EventBus
from app.models import Status
from app.motion import MotionAnalyzer, MotionParams
from app.recorder import Recorder
from app.roi import ROIManager
from app.settings import Settings

log = logging.getLogger(__name__)


@dataclass
class RuntimeState:
    detection_enabled: bool = True
    recording_enabled: bool = False
    jpeg: bytes = b""
    mask_jpeg: bytes = b""
    last_status: dict = field(default_factory=dict)


class Services:
    def __init__(
        self,
        settings: Settings,
        loop: asyncio.AbstractEventLoop,
        source_factory: Callable[[], FrameSource] | None = None,
    ) -> None:
        self.settings = settings
        self.loop = loop
        self.state = RuntimeState(
            detection_enabled=settings.detection_enabled,
            recording_enabled=settings.recording_enabled,
        )
        self.bus = EventBus(loop)
        self.roi = ROIManager(settings.roi_settings_file, list(settings.cameras.keys()))
        self.analyzer = MotionAnalyzer(MotionParams(settings.motion_threshold, settings.min_area))
        self.composer = FrameComposer(settings.display_width, settings.display_height)

        self.current_camera: str = settings.default_camera
        self._camera_lock = asyncio.Lock()

        self.recorder = Recorder(
            settings.recordings_dir,
            buffer_seconds=settings.record_buffer_seconds,
            after_seconds=settings.record_after_seconds,
            min_seconds=settings.min_record_seconds,
            max_seconds=settings.max_record_seconds,
            fps=settings.record_fps,
            keep=settings.recordings_keep,
            size=(settings.display_width, settings.display_height),
        )
        self.recorder.set_enabled(self.state.recording_enabled)

        self.audio: AudioService | None = None
        self._audio_lock = asyncio.Lock()

        self._source_factory: Callable[[], FrameSource] = source_factory or (
            lambda: OpenCVSource(self.settings.cameras[self.current_camera].url)
        )
        self.capture = CaptureService(self._source_factory, self._on_frame)

        self._analysis_interval = 1.0 / settings.analysis_fps
        self._last_analysis = 0.0
        self._last_status_publish = 0.0

    async def start(self) -> None:
        self.capture.start()
        await self._start_audio()

    async def stop(self) -> None:
        async with self._camera_lock:
            try:
                self.capture.stop()
            except Exception as e:
                log.error("Capture stop failed: %s", e)
            await self._stop_audio()
            self.recorder.stop()
        await self.bus.close()

    def _on_frame(self, frame: NDArray[np.uint8], ts: float) -> None:
        if not self.state.detection_enabled:
            return
        if ts - self._last_analysis < self._analysis_interval:
            return
        self._last_analysis = ts

        threshold, min_area = self.roi.resolve_motion_params(
            self.current_camera,
            self.settings.motion_threshold,
            self.settings.min_area,
        )
        self.analyzer.update_params(threshold, min_area)

        roi = self.roi.get(self.current_camera)
        result = self.analyzer.analyze(frame, roi)

        annotated = self.composer.annotate(
            result.frame_bgr,
            result.detected,
            result.area,
            threshold,
            min_area,
            roi,
            self.recorder.recording,
        )
        self.state.jpeg = encode_jpeg(annotated) or b""
        self.state.mask_jpeg = encode_jpeg(self.composer.mask_tile(result.mask)) or b""

        self.recorder.on_frame(annotated, result.detected, time.monotonic())
        self._publish_status(result.detected, result.area, threshold, min_area)

    def _publish_status(
        self,
        detected: bool,
        area: float,
        threshold: int,
        min_area: int,
    ) -> None:
        now = time.monotonic()
        if now - self._last_status_publish < 0.1:
            return
        self._last_status_publish = now

        status = Status(
            camera_name=self.current_camera,
            motion_detected=detected,
            motion_area=round(area, 1),
            threshold=threshold,
            min_area=min_area,
            detection_enabled=self.state.detection_enabled,
            recording=self.recorder.recording,
            recording_enabled=self.state.recording_enabled,
            has_audio=bool(self.audio and self.audio.available),
            capture_ok=self.capture.healthy,
        )
        payload = {"kind": "status", **asdict(status)}
        self.state.last_status = payload
        self.bus.publish_threadsafe(payload)

    async def switch_camera(self, name: str) -> None:
        if name not in self.settings.cameras:
            raise KeyError(name)
        if name == self.current_camera:
            return

        async with self._camera_lock:
            log.info("Switching camera -> %s", name)
            await self._stop_audio()
            try:
                self.capture.stop()
            except Exception as e:
                log.error("Cannot stop previous capture: %s", e)
                raise

            self.analyzer.reset()

            new_url = self.settings.cameras[name].url
            self.current_camera = name
            self._source_factory = lambda url=new_url: OpenCVSource(url)

            self.capture = CaptureService(self._source_factory, self._on_frame)
            self.capture.start()

            await self._start_audio()
            self.bus.publish_threadsafe({"kind": "camera", "camera_name": name})

    async def _start_audio(self) -> None:
        cfg = self.settings.cameras[self.current_camera]
        if not cfg.has_audio:
            return
        async with self._audio_lock:
            self.audio = AudioService(cfg.url)
            self.audio.start()

    async def _stop_audio(self) -> None:
        async with self._audio_lock:
            if self.audio:
                self.audio.stop()
                self.audio = None
