from __future__ import annotations

import asyncio
from typing import AsyncIterator

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
            yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                   + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/stream.mjpg")
async def stream(request: Request,
                 services: Services = Depends(get_services)) -> StreamingResponse:
    async def frames() -> AsyncIterator[bytes]:
        last = b""
        while not await request.is_disconnected():
            jpeg = services.state.jpeg
            if jpeg and jpeg is not last:
                last = jpeg
                yield last
            await asyncio.sleep(1 / 15)
    return _mjpeg(frames())


@router.get("/mask.mjpg")
async def mask(request: Request,
               services: Services = Depends(get_services)) -> StreamingResponse:
    async def frames() -> AsyncIterator[bytes]:
        last = b""
        while not await request.is_disconnected():
            jpeg = services.state.mask_jpeg
            if jpeg and jpeg is not last:
                last = jpeg
                yield last
            await asyncio.sleep(1 / 10)
    return _mjpeg(frames())


@router.get("/events")
async def events(services: Services = Depends(get_services)) -> StreamingResponse:
    async def gen() -> AsyncIterator[str]:
        async for data in services.bus.subscribe():
            yield f"data: {data}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})