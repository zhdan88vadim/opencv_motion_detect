# Tests

Run the full suite:

    pytest

Real-video tests skip silently when their clips are absent, so pytest
works on a fresh clone.

| File | Covers |
|---|---|
| test_motion.py | MotionAnalyzer on synthetic frames |
| test_roi.py | ROI model invariants + JSON persistence |
| test_recorder.py | Recorder state machine, file creation |
| test_capture_synthetic.py | Full pipeline on a scripted frame list |
| test_real_video.py | Full pipeline on real clips (skipped if missing) |
| test_api.py | FastAPI endpoints via TestClient |

## Adding a real clip

1. Drop the file into tests/data/.
2. Add (filename, expected_burst_count) to CLIPS in test_real_video.py.
3. A "burst" is one contiguous run of detected=True frames separated by
   at least one detected=False frame.

## Diagnostic runs

    # Exercise the infinite MJPEG endpoint
    MOTION_SLOW_TESTS=1 pytest -q

    # Per-frame motion timeline for one clip
    pytest -s -k dump tests/test_real_video.py
