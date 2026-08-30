from datetime import UTC, datetime # type: ignore

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.iot_event import IoTEventType


class PhysicalControllerEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: int = Field(ge=1)
    event_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    event_type: IoTEventType
    occurred_at: datetime
    device_name: str | None = Field(default=None, min_length=1, max_length=200)
    device_id: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("occurred_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Timestamp must include a timezone")
        return value.astimezone(UTC)

    @field_validator("event_type")
    @classmethod
    def require_operator_transition(cls, value: IoTEventType) -> IoTEventType:
        if value not in {
            IoTEventType.REWORK,
            IoTEventType.DOWNTIME,
            IoTEventType.RESET,
        }:
            raise ValueError("Physical controller event must change operator mode")
        return value
