from __future__ import annotations

from fastapi import Request

from app.container import Services


def get_services(request: Request) -> Services:
    """Resolve the Services container created in lifespan."""
    return request.app.state.services