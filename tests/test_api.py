from __future__ import annotations

import os
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import main as app_main
from app.settings import get_settings


class FakeSource:
    def __init__(self) -> None:
        self._i = 0

    def read(self):
        self._i += 1
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
        original_init(self, s, loop, source_factory=lambda: FakeSource())

    monkeypatch.setattr(container_mod.Services, "__init__", patched_init)

    for c in settings.cameras.values():
        c.has_audio = False

    app = app_main.create_app()
    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()


def test_cameras_endpoint(client):
    r = client.get("/api/cameras")
    assert r.status_code == 200
    data = r.json()
    assert "cameras" in data and data["selected"] in data["cameras"]


def test_roi_roundtrip(client):
    name = list(client.get("/api/cameras").json()["cameras"])[0]
    r = client.get(f"/api/roi/{name}")
    assert r.status_code == 200
    roi = {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.3, "enabled": True}
    r = client.post("/api/roi", json={"camera_name": name, "roi": roi})
    assert r.status_code == 200
    r = client.get(f"/api/roi/{name}")
    assert r.json()["enabled"] is True and abs(r.json()["x"] - 0.1) < 1e-6


def test_roi_unknown_camera_404(client):
    r = client.get("/api/roi/DoesNotExist")
    assert r.status_code == 404


def test_params_update_per_camera(client):
    name = list(client.get("/api/cameras").json()["cameras"])[0]
    r = client.post(
        "/api/params",
        json={
            "camera_name": name,
            "threshold": 300,
            "min_area": 10,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["camera_name"] == name
    assert body["threshold"] == 300
    assert body["min_area"] == 10


def test_params_requires_camera_name(client):
    r = client.post("/api/params", json={"threshold": 300})
    assert r.status_code == 422


def test_recordings_empty(client):
    r = client.get("/api/recordings")
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.skipif(
    not os.environ.get("MOTION_SLOW_TESTS"),
    reason="set MOTION_SLOW_TESTS=1 to exercise the infinite MJPEG endpoint",
)
def test_stream_returns_mjpeg(client):
    deadline = time.time() + 5.0
    got = False
    while time.time() < deadline and not got:
        with client.stream("GET", "/stream.mjpg") as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("multipart/x-mixed-replace")
            it = r.iter_bytes()
            got = next(it, None) is not None
        if not got:
            time.sleep(0.1)
    assert got, "stream produced no bytes within timeout"


def test_params_per_camera(client):
    names = list(client.get("/api/cameras").json()["cameras"])
    assert len(names) >= 2, "need at least two cameras in test config"
    a, b = names[0], names[1]

    r = client.post(
        "/api/params",
        json={
            "camera_name": a,
            "threshold": 400,
            "min_area": 15,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["threshold"] == 400
    assert body["min_area"] == 15

    r = client.get(f"/api/params/{b}")
    assert r.status_code == 200
    b_body = r.json()
    assert (b_body["threshold"], b_body["min_area"]) != (400, 15)

    r = client.get(f"/api/params/{a}")
    assert r.status_code == 200
    a_body = r.json()
    assert a_body["threshold"] == 400
    assert a_body["min_area"] == 15


def test_params_can_set_global_toggles(client):
    name = list(client.get("/api/cameras").json()["cameras"])[0]
    r = client.post(
        "/api/params",
        json={
            "camera_name": name,
            "threshold": 250,
            "detection_enabled": False,
            "recording_enabled": True,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["detection_enabled"] is False
    assert body["recording_enabled"] is True

    r = client.get("/api/status")
    # status may be empty until a frame arrives, so also check /api/params
    r = client.get(f"/api/params/{name}")
    assert r.json()["detection_enabled"] is False
    assert r.json()["recording_enabled"] is True

    # reset for other tests
    client.post(
        "/api/params",
        json={
            "camera_name": name,
            "detection_enabled": True,
            "recording_enabled": False,
        },
    )


def test_params_unknown_camera_404(client):
    r = client.post(
        "/api/params",
        json={
            "camera_name": "DoesNotExist",
            "threshold": 300,
        },
    )
    assert r.status_code == 404
    r = client.get("/api/params/DoesNotExist")
    assert r.status_code == 404
