from fastapi import APIRouter, Request

from app.api.dependencies import DatabaseDependency, SettingsDependency
from app.db.migrations import current_schema_version
from app.schemas.common import DatabaseHealthResponse, HealthResponse

router = APIRouter(tags=["Health"])


def build_health_response(request: Request, settings: SettingsDependency) -> HealthResponse:
    """Build health information from live application state."""

    ready = bool(
        getattr(request.app.state, "service_ready", False)
        and getattr(request.app.state, "security_ready", False)
    )
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
    """Return a small response used by Electron during backend startup."""

    return build_health_response(request, settings)


@router.get(
    "/health/database",
    response_model=DatabaseHealthResponse,
    summary="Check SQLite configuration and schema version",
)
def database_health(connection: DatabaseDependency) -> DatabaseHealthResponse:
    """Verify important per-connection PRAGMAs and migration state."""

    foreign_keys = bool(connection.execute("PRAGMA foreign_keys").fetchone()[0])
    journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0])
    busy_timeout_ms = int(connection.execute("PRAGMA busy_timeout").fetchone()[0])

    return DatabaseHealthResponse(
        status="ok",
        schema_version=current_schema_version(connection),
        foreign_keys=foreign_keys,
        journal_mode=journal_mode,
        busy_timeout_ms=busy_timeout_ms,
    )
