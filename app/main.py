from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.container import Services
from app.routers import ROUTERS
from app.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    loop = asyncio.get_running_loop()
    services = Services(settings, loop)
    app.state.services = services
    await services.start()
    log.info("Ready (camera=%s)", services.current_camera)
    try:
        yield
    finally:
        await services.stop()
        log.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(title="Motion Detection API", version="2.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    for router in ROUTERS:
        app.include_router(router)

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=bool(os.environ.get("DEV")))
