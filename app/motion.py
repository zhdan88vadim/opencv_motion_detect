from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

from app.models import MotionResult, ROISettings


@dataclass
class MotionParams:
    threshold: int = 200
    min_area: int = 5


class MotionAnalyzer:
    """Pure motion analysis over BGR frames. Stateless except the MOG2 model."""

    def __init__(self, params: MotionParams | None = None, history: int = 500) -> None:
        self.params = params or MotionParams()
        self._mog2 = cv2.createBackgroundSubtractorMOG2(
            history=history, varThreshold=70, detectShadows=True
        )

    def update_params(self, threshold: int | None = None, min_area: int | None = None) -> None:
        if threshold is not None:
            self.params.threshold = threshold
        if min_area is not None:
            self.params.min_area = min_area

    def reset(self) -> None:
        self._mog2 = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=70, detectShadows=True
        )

    def analyze(self, frame_bgr: NDArray[np.uint8], roi: ROISettings) -> MotionResult:
        """Return motion result. If ROI is effective, analysis is restricted to it."""
        h, w = frame_bgr.shape[:2]
        if roi.is_effective:
            x0 = int(round(roi.x * w))
            y0 = int(round(roi.y * h))
            x1 = int(round((roi.x + roi.width) * w))
            y1 = int(round((roi.y + roi.height) * h))
            x0, y0 = max(0, x0), max(0, y0)
            x1, y1 = min(w, max(x1, x0 + 1)), min(h, max(y1, y0 + 1))
            region = frame_bgr[y0:y1, x0:x1]
            offset = (x0, y0)
        else:
            region = frame_bgr
            offset = (0, 0)

        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        fg = self._mog2.apply(gray)
        # Remove shadow pixels (127) — treat only definite foreground (255).
        fg = np.where(fg == 255, 255, 0).astype(np.uint8)
        fg = cv2.medianBlur(fg, 5)

        contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        area = 0.0
        kept = 0
        for c in contours:
            a = cv2.contourArea(c)
            if a >= self.params.min_area:
                area += a
                kept += 1

        detected = area > self.params.threshold

        # Annotated frame (full-size) with boxes
        annotated = frame_bgr.copy()
        for c in contours:
            if cv2.contourArea(c) < self.params.min_area:
                continue
            cx, cy, cw, ch = cv2.boundingRect(c)
            cv2.rectangle(annotated, (cx + offset[0], cy + offset[1]),
                          (cx + offset[0] + cw, cy + offset[1] + ch), (0, 255, 0), 2)

        return MotionResult(detected=detected, area=area, contours=kept,
                            frame_bgr=annotated, mask=fg)
