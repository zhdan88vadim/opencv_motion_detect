from app.routers import audio, control, pages, recordings, roi, stream

ROUTERS = [
    pages.router,
    stream.router,
    control.router,
    roi.router,
    recordings.router,
    audio.router,
]
