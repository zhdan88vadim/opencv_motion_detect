"""End-to-end motion detection test on real short video clips with a fixed ROI.

Each clip is paired with the number of motion bursts it should produce.
A "burst" is one contiguous run of detected=True frames, i.e. one motion event.

Missing clips are skipped individually, so the file can grow incrementally.

Run with -s to see per-frame diagnostics.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from app.capture import OpenCVSource
from app.models import ROISettings
from app.motion import MotionAnalyzer, MotionParams

DATA_DIR = Path(__file__).parent / "data"

BALCONY_ROI = ROISettings(
    x=0.8083888778700411,
    y=0.09039514929542823,
    width=0.16017049398285288,
    height=0.24328471834738363,
    enabled=True,
)

CLIPS: list[tuple[str, int]] = [
    ("short_clip.mp4", 3),
    ("motion_20261023_112414_832.mp4", 2),
    ("two_motions.mp4", 2),
]


def _analyze_clip(path: Path) -> tuple[list[bool], list[float]]:
    src = OpenCVSource(str(path))
    analyzer = MotionAnalyzer(MotionParams(threshold=200, min_area=5))
    flags: list[bool] = []
    areas: list[float] = []

    try:
        first = src.read()
        assert first is not None, f"cannot decode {path}"
        h, w = first.shape[:2]
        blank = np.zeros((h, w, 3), dtype=np.uint8)
        for _ in range(10):
            analyzer.analyze(blank, BALCONY_ROI)

        for frame in [first, *_iter_rest(src)]:
            r = analyzer.analyze(frame, BALCONY_ROI)
            flags.append(r.detected)
            areas.append(r.area)
    finally:
        src.close()

    return flags, areas


def _iter_rest(src: OpenCVSource):
    while True:
        f = src.read()
        if f is None:
            return
        yield f


def _count_bursts(flags: list[bool]) -> int:
    return sum(1 for prev, cur in zip([False, *flags], flags, strict=False) if cur and not prev)


def _pattern(flags: list[bool]) -> str:
    return "".join("#" if f else "." for f in flags)


def _cases() -> list:
    return [
        pytest.param(
            DATA_DIR / name,
            expected,
            id=name,
            marks=pytest.mark.skipif(
                not (DATA_DIR / name).exists(),
                reason=f"video not found: {DATA_DIR / name}",
            ),
        )
        for name, expected in CLIPS
    ]


@pytest.mark.parametrize("clip_path,expected_bursts", _cases())
def test_clip_has_expected_bursts(clip_path: Path, expected_bursts: int) -> None:
    flags, areas = _analyze_clip(clip_path)
    detections = sum(flags)
    bursts = _count_bursts(flags)
    pattern = _pattern(flags)
    max_area = max(areas) if areas else 0.0

    print(
        f"\n{clip_path.name}: frames={len(flags)} detections={detections} "
        f"bursts={bursts} expected={expected_bursts} max_area={max_area:.1f}"
    )
    print(f"pattern: {pattern}")

    assert detections > 0, (
        f"[{clip_path.name}] no detections inside ROI; max_area={max_area:.1f}\n{pattern}"
    )
    assert bursts == expected_bursts, (
        f"[{clip_path.name}] expected {expected_bursts} burst(s), got {bursts}\n"
        f"pattern: {pattern}\nmax_area={max_area:.1f}"
    )


_DUMP_CLIP = Path(os.environ.get("MOTION_TEST_VIDEO", DATA_DIR / "one_motion.mp4")).expanduser()


@pytest.mark.skipif(not _DUMP_CLIP.exists(), reason=f"no clip at {_DUMP_CLIP}")
@pytest.mark.skipif(
    not os.environ.get("MOTION_DUMP"),
    reason="set MOTION_DUMP=1 to print per-frame timeline",
)
def test_dump_detection_timeline() -> None:
    flags, areas = _analyze_clip(_DUMP_CLIP)
    print(f"\n{_DUMP_CLIP.name}: {len(flags)} frames")
    for i, (f, a) in enumerate(zip(flags, areas, strict=False)):
        print(f"frame {i:4d}  detected={int(f)}  area={a:8.1f}")
    print(f"pattern: {_pattern(flags)}")
