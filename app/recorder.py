from __future__ import annotations

import logging
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from numpy.typing import NDArray

log = logging.getLogger(__name__)

# Try codecs in order. mp4v is preferred for .mp4; MJPG is a universal fallback
# that works even on builds without FFmpeg's mp4v encoder (older headless builds,
# some CI runners). Each candidate: (fourcc_str, extension).
_CODECS: list[tuple[str, str]] = [
    ("mp4v", ".mp4"),
    ("avc1", ".mp4"),   # H.264, only if the build has it
    ("MJPG", ".avi"),   # always available
]


class Recorder:
    """Records short clips around motion. Frames written incrementally."""

    def __init__(self, out_dir: Path, *, buffer_seconds: float, after_seconds: float,
                 min_seconds: float, max_seconds: float, fps: float, keep: int,
                 size: tuple[int, int]) -> None:
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.buffer_seconds = buffer_seconds
        self.after_seconds = after_seconds
        self.min_seconds = min_seconds
        self.max_seconds = max_seconds
        self.fps = fps
        self.keep = keep
        self.size = size

        max_frames = max(1, int(buffer_seconds * fps))
        self._buffer: deque[NDArray[np.uint8]] = deque(maxlen=max_frames)

        self._enabled = False
        self._recording = False
        self._writer: Optional[cv2.VideoWriter] = None
        self._path: Optional[Path] = None
        self._started_at = 0.0
        self._last_motion_at = 0.0
        self._lock = threading.Lock()
        self._last_error: Optional[str] = None

    # -- state --
    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def last_error(self) -> Optional[str]:
        """Populated when the last start attempt failed to open a writer."""
        return self._last_error

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = enabled
            if not enabled and self._recording:
                self._stop_locked()

    # -- public API from capture loop --
    def on_frame(self, frame: NDArray[np.uint8], motion: bool, now: float) -> None:
        with self._lock:
            self._buffer.append(frame.copy())
            if not self._enabled:
                return
            if motion:
                self._last_motion_at = now
                if not self._recording:
                    self._start_locked(now)
            if self._recording:
                self._write_locked(frame)
                duration = now - self._started_at
                quiet_for = now - self._last_motion_at
                if duration >= self.max_seconds or (
                    quiet_for >= self.after_seconds and duration >= self.min_seconds
                ):
                    self._stop_locked()

    def stop(self) -> None:
        with self._lock:
            if self._recording:
                self._stop_locked()
            self._buffer.clear()

    # -- internals --
    def _open_writer(self, stem: str) -> Optional[tuple[cv2.VideoWriter, Path]]:
        """Try each codec; return the first that opens. Updates `_last_error` on failure."""
        self._last_error = None
        last_err: Optional[str] = None
        for fourcc_str, ext in _CODECS:
            path = self.out_dir / f"{stem}{ext}"
            fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
            writer = cv2.VideoWriter(str(path), fourcc, self.fps, self.size)
            if writer.isOpened():
                return writer, path
            writer.release()
            last_err = f"codec {fourcc_str!r} failed"
        self._last_error = f"no codec available ({last_err})"
        return None

    def _start_locked(self, now: float) -> None:
        stem = "motion_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        opened = self._open_writer(stem)
        if opened is None:
            log.error("Cannot open video writer for %s: %s", stem, self._last_error)
            return
        self._writer, self._path = opened

        # pre-roll
        for f in self._buffer:
            if f.shape[1::-1] != self.size:
                f = cv2.resize(f, self.size)
            self._writer.write(f)
        self._recording = True
        self._started_at = now
        self._last_motion_at = now
        log.info("Recording started: %s", self._path.name)

    def _write_locked(self, frame: NDArray[np.uint8]) -> None:
        if not self._writer:
            return
        if frame.shape[1::-1] != self.size:
            frame = cv2.resize(frame, self.size)
        self._writer.write(frame)

    def _stop_locked(self) -> None:
        if self._writer:
            self._writer.release()
            self._writer = None

        duration = time.monotonic() - self._started_at

        if self._path is None:
            self._recording = False
            return

        if self._path.exists() and duration >= self.min_seconds:
            log.info("Recording saved: %s (%.1fs)", self._path.name, duration)
            self._prune_locked()
        elif self._path.exists():
            log.info("Recording too short, removed: %s", self._path.name)
            try:
                self._path.unlink()
            except OSError:
                pass
        else:
            log.warning("Recording file missing at stop: %s", self._path)

        self._path = None
        self._recording = False

    def _prune_locked(self) -> None:
        files = sorted(self.out_dir.glob("motion_*"), key=lambda p: p.stat().st_mtime)
        for f in files[: max(0, len(files) - self.keep)]:
            try:
                f.unlink()
            except OSError:
                pass
