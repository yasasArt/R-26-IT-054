"""FastAPI application entry point."""

import logging

from fastapi import FastAPI, Request

from app.api.dependencies import get_request_settings
from app.api.router import api_router
from app.api.routes.health import build_health_response
from app.config import Settings, get_settings
from app.lifespan import application_lifespan
from app.schemas.common import HealthResponse


def configure_logging(settings: Settings) -> None:
    """Configure readable process logging once during application creation."""

    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def create_application(settings: Settings | None = None) -> FastAPI:
    """Create an isolated FastAPI application.

    Production uses environment-backed settings. Tests pass temporary settings
    directly, preventing tests from touching the user's real database folder.
    """

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)

    application = FastAPI(
        title=resolved_settings.application_name,
        version=resolved_settings.application_version,
        description="Local application service for the Garment Counter desktop app.",
        lifespan=application_lifespan,
        docs_url="/docs" if resolved_settings.environment != "production" else None,
        redoc_url="/redoc" if resolved_settings.environment != "production" else None,
    )

    # Lifespan and request dependencies read the same application-owned object.
    application.state.settings = resolved_settings
    application.state.service_ready = False
    application.include_router(api_router)

    @application.get(
        "/health",
        response_model=HealthResponse,
        include_in_schema=False,
    )
    async def root_health(request: Request) -> HealthResponse:
        """Compatibility alias used before the versioned API is available."""

        current_settings = get_request_settings(request)
        return build_health_response(request, current_settings)

    return application


# Uvicorn imports this object when running ``uvicorn app.main:app``.
app = create_application()
