from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

from app.models import ROISettings


@pytest.fixture
def blank_frame() -> NDArray[np.uint8]:
    return np.zeros((120, 160, 3), dtype=np.uint8)


def make_motion_frame(
    h: int = 120, w: int = 160, box: tuple[int, int, int, int] = (40, 40, 40, 40)
) -> NDArray[np.uint8]:
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    x, y, bw, bh = box
    frame[y : y + bh, x : x + bw] = 255
    return frame


@pytest.fixture
def full_roi() -> ROISettings:
    return ROISettings()
