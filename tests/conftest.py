from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

from app.models import ROISettings


@pytest.fixture
def blank_frame() -> NDArray[np.uint8]:
    return np.zeros((120, 160, 3), dtype=np.uint8)


@pytest.fixture
def full_roi() -> ROISettings:
    return ROISettings()
