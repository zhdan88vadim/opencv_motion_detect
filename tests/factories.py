from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def make_motion_frame(
    h: int = 120,
    w: int = 160,
    box: tuple[int, int, int, int] = (40, 40, 40, 40),
) -> NDArray[np.uint8]:
    """Return a blank BGR frame with a white rectangle of the given box."""
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    x, y, bw, bh = box
    frame[y : y + bh, x : x + bw] = 255
    return frame
