from __future__ import annotations

import asyncio
import queue
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.container import Services
from app.deps import get_services

router = APIRouter()


@router.get("/audio.wav")
async def audio(services: Services = Depends(get_services)) -> StreamingResponse:
    if not services.audio or not services.audio.available:
        raise HTTPException(404, "Audio not available")
    svc = services.audio
    q = svc.subscribe()

    async def gen() -> AsyncIterator[bytes]:
        try:
            yield svc.header
            while True:
                try:
                    chunk = await asyncio.get_running_loop().run_in_executor(
                        None, q.get, True, 0.5,
                    )
                except queue.Empty:
                    continue
                if chunk:
                    yield chunk
        finally:
            svc.unsubscribe(q)

    return StreamingResponse(gen(), media_type="audio/wav",
                             headers={"Cache-Control": "no-cache"})