from fastapi import APIRouter, Request

from app.api.dependencies import SettingsDependency
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


def build_health_response(request: Request, settings: SettingsDependency) -> HealthResponse:

    ready = bool(getattr(request.app.state, "service_ready", False))
    return HealthResponse(
        status="ok" if ready else "starting",
        service=settings.application_name,
        version=settings.application_version,
        environment=settings.environment,
        ready=ready,
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check application-service readiness",
)
async def health_check(
    request: Request,
    settings: SettingsDependency,
) -> HealthResponse:
    
    return build_health_response(request, settings)
