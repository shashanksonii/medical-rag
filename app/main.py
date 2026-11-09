"""FastAPI application factory.

Run with::

    uvicorn app.main:create_app --factory --reload
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import __version__
from app.api import health
from app.core.config import Settings, get_settings
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware

logger = logging.getLogger(__name__)

DESCRIPTION = (
    "Backend for longitudinal medical record analysis and evidence-grounded "
    "clinical RAG (final-year B.Tech research prototype).\n\n"
    "**For medical information organisation and educational support only. "
    "It does not diagnose, recommend treatment, or replace a qualified "
    "medical professional. Use only synthetic, de-identified or authorised data.**"
)


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # The traceback is already logged by RequestContextMiddleware; never leak
    # internals (which could include report text) to the client.
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application.

    ``settings`` can be injected (used by tests); otherwise the cached
    environment-based settings are used.
    """
    settings = settings or get_settings()
    setup_logging(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "Starting %s v%s (environment=%s)",
            settings.app_name,
            __version__,
            settings.environment,
        )
        yield
        logger.info("Shutting down %s", settings.app_name)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=DESCRIPTION,
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
    app.include_router(health.router)
    return app
