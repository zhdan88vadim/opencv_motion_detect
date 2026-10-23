from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.container import Services
from app.deps import get_services
from app.models import (
    DetectionToggle,
    MotionParamsRequest,
    RecordingToggle,
    SwitchCameraRequest,
)

router = APIRouter()


@router.get("/api/cameras")
async def cameras(services: Services = Depends(get_services)) -> JSONResponse:
    return JSONResponse(
        {
            "cameras": {
                name: {"url": c.url, "has_audio": c.has_audio}
                for name, c in services.settings.cameras.items()
            },
            "selected": services.current_camera,
            "default": services.settings.default_camera,
        }
    )


@router.post("/api/camera")
async def switch_camera(
    req: SwitchCameraRequest, services: Services = Depends(get_services)
) -> JSONResponse:
    if req.name not in services.settings.cameras:
        raise HTTPException(404, f"Unknown camera: {req.name}")
    try:
        await services.switch_camera(req.name)
    except RuntimeError as e:
        raise HTTPException(409, f"Camera switch aborted: {e}")
    return JSONResponse({"camera": req.name})


@router.post("/api/detection")
async def toggle_detection(
    req: DetectionToggle, services: Services = Depends(get_services)
) -> JSONResponse:
    services.state.detection_enabled = req.enabled
    if not req.enabled:
        services.state.jpeg = b""
    return JSONResponse({"detection_enabled": req.enabled})


@router.post("/api/recording")
async def toggle_recording(
    req: RecordingToggle, services: Services = Depends(get_services)
) -> JSONResponse:
    services.state.recording_enabled = req.enabled
    services.recorder.set_enabled(req.enabled)
    return JSONResponse({"recording_enabled": req.enabled})


@router.post("/api/params")
async def params(
    req: MotionParamsRequest, services: Services = Depends(get_services)
) -> JSONResponse:
    # Global toggles — applied regardless of camera.
    if req.detection_enabled is not None:
        services.state.detection_enabled = req.detection_enabled
        if not req.detection_enabled:
            services.state.jpeg = b""

    if req.recording_enabled is not None:
        services.state.recording_enabled = req.recording_enabled
        services.recorder.set_enabled(req.recording_enabled)

    # Per-camera threshold / min_area.
    try:
        roi = services.roi.get(req.camera_name)
    except KeyError:
        raise HTTPException(404, req.camera_name)

    if req.threshold is not None:
        roi.motion_threshold = req.threshold
    if req.min_area is not None:
        roi.min_area = req.min_area
    services.roi.set(req.camera_name, roi)

    threshold, min_area = services.roi.resolve_motion_params(
        req.camera_name,
        services.settings.motion_threshold,
        services.settings.min_area,
    )
    if services.current_camera == req.camera_name:
        services.analyzer.update_params(threshold, min_area)

    return JSONResponse(
        {
            "camera_name": req.camera_name,
            "threshold": threshold,
            "min_area": min_area,
            "detection_enabled": services.state.detection_enabled,
            "recording_enabled": services.state.recording_enabled,
        }
    )


@router.get("/api/params/{camera_name}")
async def get_params(camera_name: str, services: Services = Depends(get_services)) -> JSONResponse:
    try:
        threshold, min_area = services.roi.resolve_motion_params(
            camera_name,
            services.settings.motion_threshold,
            services.settings.min_area,
        )
    except KeyError:
        raise HTTPException(404, camera_name)
    return JSONResponse(
        {
            "camera_name": camera_name,
            "threshold": threshold,
            "min_area": min_area,
            "detection_enabled": services.state.detection_enabled,
            "recording_enabled": services.state.recording_enabled,
        }
    )


@router.get("/api/status")
async def status(services: Services = Depends(get_services)) -> JSONResponse:
    return JSONResponse(services.state.last_status or {})


@router.get("/api/health")
async def health(services: Services = Depends(get_services)) -> JSONResponse:
    return JSONResponse(
        {
            "capture_ok": services.capture.healthy,
            "last_frame_age_s": max(0.0, time.monotonic() - services.capture.last_frame_ts),
            "camera": services.current_camera,
        }
    )
