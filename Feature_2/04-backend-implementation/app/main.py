import logging

from fastapi import FastAPI, Request

from app.api.dependencies import get_request_settings
from app.api.router import api_router
from app.api.routes.health import build_health_response
from app.config import Settings, get_settings
from app.lifespan import application_lifespan
from app.schemas.common import HealthResponse


def configure_logging(settings: Settings) -> None:

    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def create_application(settings: Settings | None = None) -> FastAPI:

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

    application.state.settings = resolved_settings
    application.state.service_ready = False
    application.state.database_ready = False
    application.state.schema_version = 0
    application.include_router(api_router)

    @application.get(
        "/health",
        response_model=HealthResponse,
        include_in_schema=False,
    )
    async def root_health(request: Request) -> HealthResponse:

        current_settings = get_request_settings(request)
        return build_health_response(request, current_settings)

    return application


app = create_application()
