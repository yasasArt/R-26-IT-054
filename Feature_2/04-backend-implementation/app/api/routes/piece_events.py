from datetime import UTC, datetime # type: ignore

from fastapi import APIRouter, status

from app.api.dependencies import DatabaseDependency, SettingsDependency
from app.errors import ForbiddenError
from app.schemas.piece_event import (
    EventSource,
    PieceConfirmationResponse,
    PieceEventCreate,
    PieceEventResponse,
    ProductionSummaryResponse,
    SewingStartRequest,
)
from app.schemas.session import SessionResponse
from app.services.production_service import ProductionService

router = APIRouter(prefix="/sessions", tags=["Confirmed garment events"])


def production_service(
    connection: DatabaseDependency,
    settings: SettingsDependency,
) -> ProductionService:
    return ProductionService(
        connection,
        minimum_piece_gap_seconds=settings.minimum_piece_gap_seconds,
    )


def require_simulation_allowed(settings: SettingsDependency) -> None:
    if settings.environment == "production":
        raise ForbiddenError(
            "Manual counting endpoints are disabled in production; "
            "the trusted vision pipeline must call the production service"
        )


@router.post("/{session_id}/sewing-start", response_model=SessionResponse)
def mark_first_sewing_started(
    session_id: int,
    payload: SewingStartRequest,
    connection: DatabaseDependency,
    settings: SettingsDependency,
) -> SessionResponse:
    require_simulation_allowed(settings)
    started_at = payload.started_at or datetime.now(UTC)
    return production_service(connection, settings).mark_first_sewing_started(
        session_id,
        started_at,
    )


@router.post(
    "/{session_id}/piece-events",
    response_model=PieceConfirmationResponse,
    status_code=status.HTTP_201_CREATED,
)
def confirm_test_piece(
    session_id: int,
    payload: PieceEventCreate,
    connection: DatabaseDependency,
    settings: SettingsDependency,
) -> PieceConfirmationResponse:
    require_simulation_allowed(settings)
    completed_at = payload.completed_at or datetime.now(UTC)
    return production_service(connection, settings).confirm_piece(
        session_id,
        event_key=payload.event_key,
        completed_at=completed_at,
        confidence=payload.confidence,
        event_source=EventSource.MANUAL_TEST,
    )


@router.get("/{session_id}/piece-events", response_model=list[PieceEventResponse])
def list_piece_events(
    session_id: int,
    connection: DatabaseDependency,
    settings: SettingsDependency,
) -> list[PieceEventResponse]:
    return production_service(connection, settings).list_events(session_id)


@router.get(
    "/{session_id}/production-summary",
    response_model=ProductionSummaryResponse,
)
def production_summary(
    session_id: int,
    connection: DatabaseDependency,
    settings: SettingsDependency,
) -> ProductionSummaryResponse:
    return production_service(connection, settings).summary(session_id)
