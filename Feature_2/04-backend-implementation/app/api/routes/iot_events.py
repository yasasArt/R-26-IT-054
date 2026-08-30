"""Development IoT simulation and operator-event reporting endpoints."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.dependencies import DatabaseDependency, SettingsDependency
from app.errors import ForbiddenError, InvalidOperationError
from app.schemas.iot_event import (
    IoTEventCreate,
    IoTEventResponse,
    IoTEventSource,
    IoTSummaryResponse,
    IoTTransitionResponse,
)
from app.services.iot_service import IoTService

router = APIRouter(prefix="/sessions", tags=["IoT operator events"])


def require_simulation_allowed(settings: SettingsDependency) -> None:
    if settings.environment == "production":
        raise ForbiddenError(
            "Simulated IoT endpoints are disabled in production; "
            "the trusted controller integration must call the IoT service"
        )


@router.post(
    "/{session_id}/iot-events",
    response_model=IoTTransitionResponse,
    status_code=status.HTTP_201_CREATED,
)
def simulate_iot_event(
    session_id: int,
    payload: IoTEventCreate,
    connection: DatabaseDependency,
    settings: SettingsDependency,
) -> IoTTransitionResponse:
    require_simulation_allowed(settings)
    return IoTService(connection).record_transition(
        session_id,
        event_key=payload.event_key,
        event_type=payload.event_type,
        occurred_at=payload.occurred_at or datetime.now(UTC),
        event_source=IoTEventSource.VALIDATION,
    )


@router.get("/{session_id}/iot-events", response_model=list[IoTEventResponse])
def list_iot_events(
    session_id: int,
    connection: DatabaseDependency,
) -> list[IoTEventResponse]:
    return IoTService(connection).list_events(session_id)


@router.get("/{session_id}/iot-summary", response_model=IoTSummaryResponse)
def iot_summary(
    session_id: int,
    connection: DatabaseDependency,
    as_of: Annotated[datetime | None, Query()] = None,
) -> IoTSummaryResponse:
    calculated_through = as_of or datetime.now(UTC)
    if calculated_through.utcoffset() is None:
        raise InvalidOperationError("The as_of timestamp must include a timezone")
    return IoTService(connection).summary(
        session_id,
        calculated_through=calculated_through,
    )
