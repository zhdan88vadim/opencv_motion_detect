from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class CameraConfig(BaseModel):
    url: str
    has_audio: bool = False


class Settings(BaseModel):
    cameras: dict[str, CameraConfig]
    default_camera: str
    recordings_dir: Path = Path("recordings")
    roi_settings_file: Path = Path("roi_settings.json")
    recordings_keep: int = 100

    display_width: int = Field(800, ge=160)
    display_height: int = Field(600, ge=120)

    # Motion
    motion_threshold: int = Field(200, ge=1)
    min_area: int = Field(5, ge=1)
    analysis_fps: float = Field(5.0, gt=0.1, le=30.0)

    # Recording
    record_buffer_seconds: float = 2.0
    record_after_seconds: float = 3.0
    min_record_seconds: float = 3.0
    max_record_seconds: float = 300.0
    record_fps: float = 10.0

    # Runtime defaults (overridable via API, still validated here)
    detection_enabled: bool = True
    recording_enabled: bool = False

    @classmethod
    def load(cls, path: str | Path | None = None) -> Settings:
        path = Path(path or os.environ.get("APP_SETTINGS", "settings.yaml"))
        if path.exists():
            raw: dict[str, Any] = yaml.safe_load(path.read_text())
        else:
            raw = _default_raw()
        return cls.model_validate(raw)


def _default_raw() -> dict[str, Any]:
    return {
        "cameras": {
            "Kitchen": {"url": "rtsp://192.168.0.102:8554/h1_long_1_h264", "has_audio": True},
            "H40": {"url": "rtsp://192.168.0.102:8554/h40_long_1_h264", "has_audio": True},
            "Hikvision": {
                "url": "rtsp://192.168.0.102:8554/hikvision_room_sub",
                "has_audio": False,
            },
        },
        "default_camera": "Balcony",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings.load()
