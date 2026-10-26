from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models import ROISettings
from app.roi import ROIManager


def test_roi_clamps_overflow():
    r = ROISettings(x=0.9, y=0.9, width=0.5, height=0.5, enabled=True)
    assert r.x + r.width <= 1.0 + 1e-9
    assert r.y + r.height <= 1.0 + 1e-9


def test_roi_effective_flag():
    assert ROISettings().is_effective is False
    assert ROISettings(x=0.1, y=0.1, width=0.2, height=0.2, enabled=True).is_effective is True
    # Full frame, even if enabled, is not "effective"
    assert ROISettings(enabled=True).is_effective is False


def test_manager_persists_and_cleans_unknown(tmp_path: Path):
    path = tmp_path / "roi.json"
    path.write_text(
        json.dumps(
            {
                "CamA": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2, "enabled": True},
                "Bogus": {"x": 0, "y": 0, "width": 1, "height": 1, "enabled": True},
                "Сorridor": {"x": 0, "y": 0, "width": 1, "height": 1, "enabled": True},
            }
        )
    )
    mgr = ROIManager(path, camera_names=["CamA", "CamB"])
    assert mgr.get("CamA").enabled is True
    assert mgr.get("CamB").enabled is False  # default

    # File is rewritten without unknown keys
    saved = json.loads(path.read_text())
    assert "Bogus" not in saved and "Сorridor" not in saved


def test_manager_rejects_unknown(tmp_path: Path):
    mgr = ROIManager(tmp_path / "r.json", camera_names=["A"])
    with pytest.raises(KeyError):
        mgr.set("B", ROISettings())


def test_per_camera_motion_params_resolution(tmp_path: Path):
    mgr = ROIManager(tmp_path / "roi.json", camera_names=["A", "B"])
    assert mgr.resolve_motion_params("A", 200, 5) == (200, 5)
    assert mgr.resolve_motion_params("B", 200, 5) == (200, 5)

    roi = mgr.get("A")
    roi.motion_threshold = 500
    roi.min_area = 20
    mgr.set("A", roi)

    assert mgr.resolve_motion_params("A", 200, 5) == (500, 20)
    assert mgr.resolve_motion_params("B", 200, 5) == (200, 5)


def test_per_camera_motion_params_persist(tmp_path: Path):
    path = tmp_path / "roi.json"
    mgr = ROIManager(path, camera_names=["A"])
    roi = mgr.get("A")
    roi.motion_threshold = 300
    mgr.set("A", roi)

    mgr2 = ROIManager(path, camera_names=["A"])
    assert mgr2.get("A").motion_threshold == 300


def test_resolve_motion_params_unknown_camera(tmp_path: Path):
    mgr = ROIManager(tmp_path / "roi.json", camera_names=["A"])
    with pytest.raises(KeyError):
        mgr.resolve_motion_params("B", 200, 5)
