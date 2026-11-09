"""Health-check endpoint."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import __version__
from app.core.config import Settings, get_settings

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Basic service health information."""

    status: Literal["ok"]
    service: str
    version: str
    environment: str
    timestamp: datetime


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
)
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """Return ``ok`` when the API process is up and able to serve requests.

    This milestone checks only the API process itself. Database and model
    checks will be added in the milestones that introduce those components.
    """
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=__version__,
        environment=settings.environment,
        timestamp=datetime.now(timezone.utc),
    )
