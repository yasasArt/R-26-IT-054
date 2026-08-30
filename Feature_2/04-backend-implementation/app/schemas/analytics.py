from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.iot_event import IoTEventSource, IoTEventType
from app.schemas.piece_event import EventSource
from app.schemas.session import OperatorMode, SessionMode, SessionStatus


class AnalyticsFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: int | None = Field(default=None, ge=1)
    employee_id: int | None = Field(default=None, ge=1)
    date_from: date | None = None
    date_to: date | None = None
    session_status: SessionStatus | None = None
    session_mode: SessionMode | None = None

    @model_validator(mode="after")
    def require_valid_date_range(self) -> "AnalyticsFilters":
        if (
            self.date_from is not None
            and self.date_to is not None
            and self.date_from > self.date_to
        ):
            raise ValueError("date_from cannot be after date_to")
        return self


class PieceCycleAnalytics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: int
    piece_number: int
    cycle_seconds: float
    confidence: float | None
    event_source: EventSource
    sewing_started_at: datetime | None
    completed_at: datetime


class OperatorEventAnalytics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: int
    event_type: IoTEventType
    mode_before: OperatorMode
    mode_after: OperatorMode
    device_name: str | None
    event_source: IoTEventSource
    occurred_at: datetime
    closed_mode_duration_seconds: float | None


class ActivityAnalytics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int
    duration_seconds: float


class SessionAnalytics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: int
    employee_id: int
    employee_number: str
    employee_name: str
    sewing_line: str
    session_mode: SessionMode
    session_status: SessionStatus
    operator_mode: OperatorMode
    started_at: datetime
    ended_at: datetime | None
    target_pieces: int
    confirmed_pieces: int
    remaining_pieces: int
    achievement_percent: float
    average_cycle_seconds: float | None
    individual_cycle_times: list[PieceCycleAnalytics]
    rework: ActivityAnalytics
    downtime: ActivityAnalytics
    operator_events: list[OperatorEventAnalytics]


class ManagementSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_sessions: int
    unique_employees: int
    active_sessions: int
    completed_sessions: int
    cancelled_sessions: int
    target_pieces: int
    confirmed_pieces: int
    remaining_pieces: int
    achievement_percent: float
    average_cycle_seconds: float | None
    rework_count: int
    rework_duration_seconds: float
    downtime_count: int
    downtime_duration_seconds: float


class AnalyticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    filters: AnalyticsFilters
    summary: ManagementSummary
    sessions: list[SessionAnalytics]


class SessionHistoryDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: int
    deleted_piece_events: int
    deleted_iot_events: int
    deleted_sessions: int

