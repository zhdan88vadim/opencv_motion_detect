from __future__ import annotations

from app.models import ROISettings
from app.motion import MotionAnalyzer, MotionParams


def _feed(analyzer: MotionAnalyzer, frames, roi: ROISettings):
    last = None
    for f in frames:
        last = analyzer.analyze(f, roi)
    return last


def test_no_motion_on_static(blank_frame, full_roi):
    a = MotionAnalyzer(MotionParams(threshold=10, min_area=5))
    result = _feed(a, [blank_frame.copy() for _ in range(30)], full_roi)
    assert result.detected is False
    assert result.area == 0


def test_motion_detected_on_change(blank_frame, full_roi):
    from tests.conftest import make_motion_frame

    a = MotionAnalyzer(MotionParams(threshold=10, min_area=5))
    warmup = [blank_frame.copy() for _ in range(30)]
    moving = make_motion_frame()
    r = _feed(a, warmup + [moving, moving, moving], full_roi)
    assert r.detected is True
    assert r.area > 10


def test_roi_limits_detection(blank_frame):
    from tests.conftest import make_motion_frame

    # ROI covers left half only
    roi = ROISettings(x=0.0, y=0.0, width=0.5, height=1.0, enabled=True)
    a = MotionAnalyzer(MotionParams(threshold=10, min_area=5))
    warmup = [blank_frame.copy() for _ in range(30)]
    # Motion in right half -> outside ROI
    right = make_motion_frame(box=(120, 40, 30, 30))
    r = _feed(a, warmup + [right, right, right], roi)
    assert r.detected is False

    # Motion in left half -> inside ROI
    a2 = MotionAnalyzer(MotionParams(threshold=10, min_area=5))
    left = make_motion_frame(box=(20, 40, 30, 30))
    r2 = _feed(a2, warmup + [left, left, left], roi)
    assert r2.detected is True


def test_min_area_filters_small_objects(blank_frame, full_roi):
    from tests.conftest import make_motion_frame

    a = MotionAnalyzer(MotionParams(threshold=1, min_area=2000))
    warmup = [blank_frame.copy() for _ in range(30)]
    tiny = make_motion_frame(box=(10, 10, 5, 5))
    r = _feed(a, warmup + [tiny, tiny, tiny], full_roi)
    assert r.detected is False
