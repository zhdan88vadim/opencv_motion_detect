from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.container import Services
from app.deps import get_services
from app.models import ROISetRequest

router = APIRouter()


@router.get("/api/roi/{camera_name}")
async def get_roi(camera_name: str, services: Services = Depends(get_services)) -> JSONResponse:
    try:
        return JSONResponse(services.roi.get(camera_name).model_dump())
    except KeyError as e:
        raise HTTPException(404, camera_name) from e


@router.post("/api/roi")
async def set_roi(req: ROISetRequest, services: Services = Depends(get_services)) -> JSONResponse:
    try:
        services.roi.set(req.camera_name, req.roi)
    except KeyError as e:
        raise HTTPException(404, req.camera_name) from e
    return JSONResponse(req.roi.model_dump())


@router.post("/api/roi/{camera_name}/reset")
async def reset_roi(camera_name: str, services: Services = Depends(get_services)) -> JSONResponse:
    try:
        services.roi.reset(camera_name)
    except KeyError as e:
        raise HTTPException(404, camera_name) from e
    return JSONResponse(services.roi.get(camera_name).model_dump())
