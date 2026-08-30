from fastapi import APIRouter, status

from app.api.dependencies import DatabaseDependency
from app.schemas.iot_event import IoTEventSource, IoTTransitionResponse
from app.schemas.trusted import PhysicalControllerEvent
from app.services.iot_service import IoTService

router = APIRouter(prefix="/trusted", tags=["Trusted desktop integrations"])


@router.post(
    "/controller-events",
    response_model=IoTTransitionResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def record_physical_controller_event(
    payload: PhysicalControllerEvent,
    connection: DatabaseDependency,
) -> IoTTransitionResponse:
    """Persist a validated device transition from Electron main, never React."""

    return IoTService(connection).record_transition(
        payload.session_id,
        event_key=payload.event_key,
        event_type=payload.event_type,
        occurred_at=payload.occurred_at,
        event_source=IoTEventSource.PHYSICAL_CONTROLLER,
        device_name=payload.device_name,
        device_id=payload.device_id,
    )
