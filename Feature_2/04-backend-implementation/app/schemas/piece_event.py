from datetime import UTC, datetime # type: ignore
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventSource(str, Enum):
    VISION = "VISION"
    VALIDATION = "VALIDATION"
    MANUAL_TEST = "MANUAL_TEST"


class AwareTimestampModel(BaseModel):
    @field_validator("started_at", "completed_at", check_fields=False)
    @classmethod
    def require_aware_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.utcoffset() is None:
            raise ValueError("Timestamp must include a timezone")
        return value.astimezone(UTC)


class SewingStartRequest(AwareTimestampModel):
    model_config = ConfigDict(extra="forbid")

    started_at: datetime | None = None


class PieceEventCreate(AwareTimestampModel):
    model_config = ConfigDict(extra="forbid")

    event_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    completed_at: datetime | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class PieceEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    session_id: int
    employee_id: int
    piece_number: int
    event_key: str | None
    sewing_started_at: datetime | None
    cycle_seconds: float
    confidence: float | None
    event_source: EventSource
    completed_at: datetime
    created_at: datetime


class ProductionSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: int
    status: str
    operator_mode: str
    target_pieces: int
    total_pieces: int
    remaining_pieces: int
    achievement_percent: float
    average_cycle_seconds: float | None
    latest_piece_at: datetime | None


class PieceConfirmationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: PieceEventResponse
    summary: ProductionSummaryResponse
    duplicate: bool
