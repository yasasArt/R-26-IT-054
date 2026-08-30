"""Contracts for operator-mode events and duration summaries."""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.session import OperatorMode, SessionResponse


class IoTEventType(str, Enum):
    REWORK = "REWORK"
    DOWNTIME = "DOWNTIME"
    RESET = "RESET"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"


class IoTEventSource(str, Enum):
    PHYSICAL_CONTROLLER = "PHYSICAL_CONTROLLER"
    VALIDATION = "VALIDATION"
    SYSTEM = "SYSTEM"


class IoTEventCreate(BaseModel):
    """Development-only payload used before Bluetooth integration."""

    model_config = ConfigDict(extra="forbid")

    event_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    event_type: IoTEventType
    occurred_at: datetime | None = None

    @field_validator("occurred_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.utcoffset() is None:
            raise ValueError("Timestamp must include a timezone")
        return value.astimezone(UTC)


class IoTEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    session_id: int
    employee_id: int
    event_key: str | None
    event_type: IoTEventType
    mode_before: OperatorMode
    mode_after: OperatorMode
    device_name: str | None
    device_id: str | None
    event_source: IoTEventSource
    occurred_at: datetime
    created_at: datetime


class IoTTransitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: IoTEventResponse
    session: SessionResponse
    duplicate: bool
    closed_mode_duration_seconds: float | None


class ModeDurationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int
    duration_seconds: float


class IoTSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: int
    current_mode: OperatorMode
    rework: ModeDurationSummary
    downtime: ModeDurationSummary
    active_mode_started_at: datetime | None
    calculated_through: datetime

