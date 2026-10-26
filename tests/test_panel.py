from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import main as app_main
from app.composer import FrameComposer
from app.models import ROISettings
from app.settings import get_settings


class _FakeSource:
    def read(self):
        return np.zeros((60, 80, 3), dtype=np.uint8)

    def close(self):
        pass


@pytest.fixture
def client(monkeypatch, tmp_path):
    get_settings.cache_clear()
    settings = get_settings()
    settings.recordings_dir = tmp_path / "rec"
    settings.roi_settings_file = tmp_path / "roi.json"

    from app import container as container_mod

    original_init = container_mod.Services.__init__

    def patched_init(self, s, loop, source_factory=None):
        original_init(self, s, loop, source_factory=lambda: _FakeSource())

    monkeypatch.setattr(container_mod.Services, "__init__", patched_init)

    for c in settings.cameras.values():
        c.has_audio = False

    app = app_main.create_app()
    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()


def test_roi_tile_placeholder_when_roi_off():
    composer = FrameComposer(80, 60)
    frame = np.zeros((60, 80, 3), dtype=np.uint8)
    tile = composer.roi_tile(frame, ROISettings(), detected=False, motion_area=0.0)
    assert tile.shape == (60, 80, 3)
    assert tile.dtype == np.uint8


def test_roi_tile_crop_matches_display_size():
    composer = FrameComposer(80, 60)
    frame = np.zeros((60, 80, 3), dtype=np.uint8)
    roi = ROISettings(x=0.1, y=0.1, width=0.4, height=0.4, enabled=True)
    tile = composer.roi_tile(frame, roi, detected=True, motion_area=100.0)
    assert tile.shape == (60, 80, 3)


def test_panel_endpoint_roundtrip(client):
    r = client.get("/api/panel")
    assert r.status_code == 200
    assert r.json()["panel_mode"] == "mask"

    r = client.post("/api/panel", json={"mode": "roi"})
    assert r.status_code == 200
    assert r.json()["panel_mode"] == "roi"

    r = client.get("/api/panel")
    assert r.json()["panel_mode"] == "roi"


def test_panel_endpoint_rejects_unknown_mode(client):
    r = client.post("/api/panel", json={"mode": "bogus"})
    assert r.status_code == 422
