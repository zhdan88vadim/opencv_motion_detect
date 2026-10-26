from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

from app.models import ROISettings


class FrameComposer:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height

    def _resize(self, frame: NDArray[np.uint8]) -> NDArray[np.uint8]:
        return cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)

    def annotate(
        self,
        frame: NDArray[np.uint8],
        detected: bool,
        area: float,
        threshold: int,
        min_area: int,
        roi: ROISettings,
        recording: bool,
    ) -> NDArray[np.uint8]:
        out = self._resize(frame)
        h, w = out.shape[:2]

        if roi.is_effective:
            x0, y0 = int(roi.x * w), int(roi.y * h)
            x1 = int((roi.x + roi.width) * w)
            y1 = int((roi.y + roi.height) * h)
            cv2.rectangle(out, (x0, y0), (x1, y1), (0, 220, 255), 2)
            cv2.putText(
                out, "ROI", (x0 + 6, y0 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 255), 2
            )

        color = (0, 0, 255) if detected else (150, 150, 150)
        text = f"MOTION {area:.0f}" if detected else "NO MOTION"
        cv2.putText(out, text, (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        cv2.putText(
            out,
            f"thr={threshold} min={min_area}",
            (12, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            1,
        )
        if recording:
            cv2.circle(out, (w - 30, 30), 8, (0, 0, 255), -1)
            cv2.putText(out, "REC", (w - 70, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        return out

    def mask_tile(self, mask: NDArray[np.uint8]) -> NDArray[np.uint8]:
        colored = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        return self._resize(colored)

    def roi_tile(
        self,
        frame: NDArray[np.uint8],
        roi: ROISettings,
        *,
        detected: bool,
        motion_area: float,
    ) -> NDArray[np.uint8]:
        """Zoomed crop of the ROI area, or a placeholder when ROI is off."""
        if not roi.is_effective:
            placeholder = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            cv2.putText(
                placeholder,
                "ROI AREA",
                (self.width // 4, self.height // 2 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.2,
                (110, 110, 110),
                3,
            )
            cv2.putText(
                placeholder,
                "ROI DISABLED",
                (self.width // 4, self.height // 2 + 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (90, 90, 90),
                2,
            )
            cv2.putText(
                placeholder,
                "Draw and enable ROI",
                (self.width // 4, self.height // 2 + 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (70, 70, 70),
                2,
            )
            return placeholder

        h, w = frame.shape[:2]
        x0 = max(0, int(round(roi.x * w)))
        y0 = max(0, int(round(roi.y * h)))
        x1 = min(w, int(round((roi.x + roi.width) * w)))
        y1 = min(h, int(round((roi.y + roi.height) * h)))

        if x1 <= x0 or y1 <= y0:
            return np.zeros((self.height, self.width, 3), dtype=np.uint8)

        crop = frame[y0:y1, x0:x1]
        if not detected:
            crop = cv2.convertScaleAbs(crop, alpha=0.3, beta=0)

        out = cv2.resize(crop, (self.width, self.height), interpolation=cv2.INTER_NEAREST)

        cv2.putText(out, "ROI ZOOM", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 255), 2)
        cv2.putText(
            out,
            f"pos=({roi.x:.2f},{roi.y:.2f}) size=({roi.width:.2f}x{roi.height:.2f})",
            (10, 58),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 220, 255),
            1,
        )
        cv2.putText(
            out,
            f"area={motion_area:.0f}",
            (10, 82),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255) if detected else (150, 150, 150),
            1,
        )
        return out


def encode_jpeg(frame: NDArray[np.uint8], quality: int = 70) -> bytes | None:
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes() if ok else None
