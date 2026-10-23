from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional, Protocol

import cv2
import numpy as np
from numpy.typing import NDArray

log = logging.getLogger(__name__)


class FrameSource(Protocol):
    """Anything that produces BGR frames. Lets tests inject synthetic video."""
    def read(self) -> Optional[NDArray[np.uint8]]: ...
    def close(self) -> None: ...


class OpenCVSource:
    """Owns a cv2.VideoCapture. Must be closed from the same thread that reads.

    Sets bounded open/read timeouts so a dead RTSP endpoint can't block
    teardown indefinitely.
    """

    def __init__(self, url: str | int,
                 open_timeout_ms: int = 3000,
                 read_timeout_ms: int = 3000) -> None:
        self.url = url
        self._open_timeout_ms = open_timeout_ms
        self._read_timeout_ms = read_timeout_ms
        self._cap: Optional[cv2.VideoCapture] = None
        self._open()

    def _open(self) -> None:
        self.close()
        # OPEN/READ timeouts must be set via cv2.CAP_PROP_* AFTER creation
        # but BEFORE open() for FFmpeg in recent OpenCV.
        cap = cv2.VideoCapture()
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self._open_timeout_ms)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, self._read_timeout_ms)
        ok = cap.open(self.url, cv2.CAP_FFMPEG)
        if not ok or not cap.isOpened():
            cap.release()
            raise RuntimeError(f"Cannot open {self.url!r}")
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap = cap

    def read(self) -> Optional[NDArray[np.uint8]]:
        cap = self._cap
        if cap is None:
            return None
        ok, frame = cap.read()
        if not ok or frame is None or frame.size == 0:
            return None
        return frame

    def close(self) -> None:
        cap = self._cap
        self._cap = None
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass


class CaptureService:
    """Single-threaded reader. The thread is the SOLE owner of the source.

    - stop() signals and joins the thread. The thread closes the source.
    - The caller must never touch the source; it is created and destroyed
      inside _run.
    - If the thread does not exit within stop_timeout, we raise instead of
      silently continuing (a hung capture thread will race on cv2 otherwise).
    """

    def __init__(self,
                 source_factory: Callable[[], FrameSource],
                 on_frame: Callable[[NDArray[np.uint8], float], None],
                 *, stop_timeout: float = 5.0) -> None:
        self._factory = source_factory
        self._on_frame = on_frame
        self._stop_timeout = stop_timeout
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._healthy = False
        self._last_frame_ts = 0.0
        self._source: Optional[FrameSource] = None

    @property
    def healthy(self) -> bool:
        return self._healthy

    @property
    def last_frame_ts(self) -> float:
        return self._last_frame_ts

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("CaptureService already running")
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout=self._stop_timeout)
            if t.is_alive():
                # Do NOT proceed: touching cv2 from a second thread is UB.
                raise RuntimeError(
                    "Capture thread did not stop within "
                    f"{self._stop_timeout}s; cannot safely reinitialize"
                )
        self._thread = None
        self._source = None

    # -- loop (runs on the capture thread) --
    def _run(self) -> None:
        backoff = 1.0
        try:
            while not self._stop.is_set():
                if self._source is None:
                    try:
                        self._source = self._factory()
                        self._healthy = True
                        backoff = 1.0
                        log.info("Capture source opened")
                    except Exception as e:
                        self._healthy = False
                        log.warning("Capture open failed: %s (retry in %.1fs)", e, backoff)
                        self._stop.wait(backoff)
                        backoff = min(backoff * 1.5, 10.0)
                        continue

                frame = self._source.read()
                if frame is None:
                    log.warning("Frame read failed; reopening")
                    self._healthy = False
                    try:
                        self._source.close()
                    except Exception:
                        pass
                    self._source = None
                    self._stop.wait(0.5)
                    continue

                self._last_frame_ts = time.monotonic()
                try:
                    self._on_frame(frame, self._last_frame_ts)
                except Exception as e:
                    log.exception("on_frame callback error: %s", e)
        finally:
            # Thread owns the source. Close it here, nowhere else.
            if self._source is not None:
                try:
                    self._source.close()
                except Exception:
                    pass
                self._source = None
            self._healthy = False
