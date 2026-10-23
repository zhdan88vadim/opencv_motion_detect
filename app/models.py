from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# ---------- ROI ----------


class ROISettings(BaseModel):
    """Per-camera ROI and motion parameters.

    ROI is normalized to [0, 1] with invariant: x + width <= 1,
    y + height <= 1.

    motion_threshold and min_area are per-camera overrides. None means
    "use the global default from settings.yaml".
    """

    x: float = Field(0.0, ge=0.0, le=1.0)
    y: float = Field(0.0, ge=0.0, le=1.0)
    width: float = Field(1.0, ge=0.0, le=1.0)
    height: float = Field(1.0, ge=0.0, le=1.0)
    enabled: bool = False

    motion_threshold: int | None = Field(None, ge=1)
    min_area: int | None = Field(None, ge=1)

    @model_validator(mode="after")
    def _clamp(self) -> ROISettings:
        self.width = min(self.width, 1.0 - self.x)
        self.height = min(self.height, 1.0 - self.y)
        return self

    @property
    def is_effective(self) -> bool:
        return (
            self.enabled
            and self.width > 0
            and self.height > 0
            and (self.x > 0 or self.y > 0 or self.width < 1 or self.height < 1)
        )


class ROISetRequest(BaseModel):
    camera_name: str
    roi: ROISettings


# ---------- Runtime control ----------


class DetectionToggle(BaseModel):
    enabled: bool


class RecordingToggle(BaseModel):
    enabled: bool


class MotionParamsRequest(BaseModel):
    """Settings request for POST /api/params.

    camera_name is required: threshold and min_area are always per-camera.
    detection_enabled and recording_enabled are global and may be omitted.
    """

    camera_name: str
    threshold: int | None = Field(None, ge=1)
    min_area: int | None = Field(None, ge=1)
    detection_enabled: bool | None = None
    recording_enabled: bool | None = None


class SwitchCameraRequest(BaseModel):
    name: str


# ---------- Results / events ----------


@dataclass(frozen=True)
class MotionResult:
    detected: bool
    area: float
    contours: int
    frame_bgr: object
    mask: object


@dataclass(frozen=True)
class Status:
    camera_name: str
    motion_detected: bool
    motion_area: float
    threshold: int
    min_area: int
    detection_enabled: bool
    recording: bool
    recording_enabled: bool
    has_audio: bool
    capture_ok: bool

    def as_dict(self) -> dict:
        return self.__dict__.copy()


EventKind = Literal["status", "recording", "camera", "error"]


@dataclass(frozen=True)
class Event:
    kind: EventKind
    payload: dict
