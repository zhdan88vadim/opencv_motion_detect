from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.container import Services
from app.deps import get_services

router = APIRouter()


def _mjpeg(frames: AsyncIterator[bytes]) -> StreamingResponse:
    async def gen() -> AsyncIterator[bytes]:
        async for jpeg in frames:
            if not jpeg:
                await asyncio.sleep(0.05)
                continue
            yield (
                b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                + str(len(jpeg)).encode()
                + b"\r\n\r\n"
                + jpeg
                + b"\r\n"
            )

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


def _stream_jpeg(
    request: Request, get_bytes: Callable[[], bytes], *, fps: int = 15
) -> StreamingResponse:
    async def frames() -> AsyncIterator[bytes]:
        last = b""
        while not await request.is_disconnected():
            jpeg = get_bytes()
            if jpeg and jpeg is not last:
                last = jpeg
                yield last
            await asyncio.sleep(1 / fps)

    return _mjpeg(frames())


@router.get("/stream.mjpg")
async def stream(request: Request, services: Services = Depends(get_services)) -> StreamingResponse:
    return _stream_jpeg(request, lambda: services.state.jpeg)


@router.get("/mask.mjpg")
async def mask(request: Request, services: Services = Depends(get_services)) -> StreamingResponse:
    return _stream_jpeg(request, lambda: services.state.mask_jpeg)


@router.get("/roi.mjpg")
async def roi(request: Request, services: Services = Depends(get_services)) -> StreamingResponse:
    return _stream_jpeg(request, lambda: services.state.roi_jpeg)


@router.get("/panel.mjpg")
async def panel(request: Request, services: Services = Depends(get_services)) -> StreamingResponse:
    return _stream_jpeg(request, lambda: services.state.panel_jpeg)


@router.get("/events")
async def events(services: Services = Depends(get_services)) -> StreamingResponse:
    async def gen() -> AsyncIterator[str]:
        async for data in services.bus.subscribe():
            yield f"data: {data}\n\n"

    return StreamingResponse(
        gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )
