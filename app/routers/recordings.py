from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.container import Services
from app.deps import get_services

router = APIRouter()


def _recording_path(services: Services, name: str) -> Path:
    """Resolve a recording name under recordings_dir, rejecting traversal."""
    if "/" in name or "\\" in name or not name.startswith("motion_"):
        raise HTTPException(404, name)
    base = services.settings.recordings_dir.resolve()
    p = (base / name).resolve()
    if not p.is_relative_to(base) or not p.exists():
        raise HTTPException(404, name)
    return p


@router.get("/api/recordings")
async def list_recordings(services: Services = Depends(get_services)) -> JSONResponse:
    d = services.settings.recordings_dir
    items = []
    if d.exists():
        # Recorder falls back to MJPG/.avi on codec-less builds, so glob both.
        paths = [*d.glob("motion_*.mp4"), *d.glob("motion_*.avi")]
        for p in sorted(paths, key=lambda x: x.stat().st_mtime, reverse=True):
            st = p.stat()
            items.append({"name": p.name, "size": st.st_size, "mtime": st.st_mtime})
    return JSONResponse({"items": items})


@router.get("/api/recordings/{name}")
async def get_recording(name: str, services: Services = Depends(get_services)) -> FileResponse:
    p = _recording_path(services, name)
    media = "video/mp4" if p.suffix == ".mp4" else "video/x-msvideo"
    return FileResponse(p, media_type=media, filename=name)


@router.delete("/api/recordings/{name}")
async def delete_recording(name: str, services: Services = Depends(get_services)) -> JSONResponse:
    p = _recording_path(services, name)
    p.unlink()
    return JSONResponse({"deleted": name})
