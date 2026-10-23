from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.container import Services
from app.deps import get_services

router = APIRouter()


@router.get("/api/recordings")
async def list_recordings(services: Services = Depends(get_services)) -> JSONResponse:
    d = services.settings.recordings_dir
    items = []
    if d.exists():
        for p in sorted(d.glob("motion_*.mp4"),
                        key=lambda x: x.stat().st_mtime, reverse=True):
            st = p.stat()
            items.append({"name": p.name, "size": st.st_size, "mtime": st.st_mtime})
    return JSONResponse({"items": items})


@router.get("/api/recordings/{name}")
async def get_recording(name: str,
                        services: Services = Depends(get_services)) -> FileResponse:
    if "/" in name or not name.startswith("motion_"):
        raise HTTPException(404, name)
    p = services.settings.recordings_dir / name
    if not p.exists():
        raise HTTPException(404, name)
    return FileResponse(p, media_type="video/mp4", filename=name)


@router.delete("/api/recordings/{name}")
async def delete_recording(name: str,
                           services: Services = Depends(get_services)) -> JSONResponse:
    if "/" in name:
        raise HTTPException(404, name)
    p = services.settings.recordings_dir / name
    if not p.exists():
        raise HTTPException(404, name)
    p.unlink()
    return JSONResponse({"deleted": name})