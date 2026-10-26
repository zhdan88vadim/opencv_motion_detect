from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from app.recorder import Recorder


def _rec(tmp_path: Path, **kw):
    defaults = dict(
        buffer_seconds=0.2,
        after_seconds=0.2,
        min_seconds=0.1,
        max_seconds=1.0,
        fps=10,
        keep=5,
        size=(64, 48),
    )
    defaults.update(kw)
    return Recorder(tmp_path, **defaults)


def _frame() -> np.ndarray:
    return np.full((48, 64, 3), 128, dtype=np.uint8)


def test_recording_requires_motion_and_writes_file(tmp_path: Path):
    r = _rec(tmp_path, min_seconds=0.0)
    r.set_enabled(True)
    now = time.monotonic()

    # First three frames: no motion, should not start recording.
    for _ in range(3):
        r.on_frame(_frame(), motion=False, now=now)
        now += 0.05
    assert r.recording is False

    # Motion frames: recording should start on the first one.
    for _ in range(10):
        r.on_frame(_frame(), motion=True, now=now)
        now += 0.05
    assert r.recording is True, f"expected recording to start; writer error was: {r.last_error!r}"

    # Quiet long enough for the after_seconds window to elapse -> stop.
    for _ in range(10):
        r.on_frame(_frame(), motion=False, now=now)
        now += 0.05
    assert r.recording is False

    files = list(tmp_path.glob("motion_*"))
    if not files:
        pytest.skip(f"no video codec available in this OpenCV build; last_error={r.last_error!r}")
    assert files[0].stat().st_size > 0


def test_disabled_does_not_record(tmp_path: Path):
    r = _rec(tmp_path, min_seconds=0.0)
    r.set_enabled(False)
    now = time.monotonic()
    for _ in range(20):
        r.on_frame(_frame(), motion=True, now=now)
        now += 0.05
    assert r.recording is False
    assert not list(tmp_path.glob("motion_*"))
