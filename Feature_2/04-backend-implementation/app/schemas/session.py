from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SessionMode(str, Enum):
    PRODUCTION = "PRODUCTION"
    VALIDATION = "VALIDATION"


class SessionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class OperatorMode(str, Enum):
    NORMAL = "NORMAL"
    REWORK = "REWORK"
    DOWNTIME = "DOWNTIME"


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: int = Field(ge=1)
    target_pieces: int = Field(ge=1, le=1_000_000)
    session_mode: SessionMode = SessionMode.PRODUCTION


class SessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    employee_id: int
    employee_number_snapshot: str
    employee_name_snapshot: str
    sewing_line_snapshot: str
    target_pieces: int
    session_mode: SessionMode
    status: SessionStatus
    operator_mode: OperatorMode
    camera_index_snapshot: int | None
    camera_label_snapshot: str | None
    controller_device_id_snapshot: str | None
    controller_name_snapshot: str | None
    total_pieces: int
    average_cycle_seconds: float | None
    first_sewing_started_at: datetime | None
    started_at: datetime
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SessionReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_mode: SessionMode
    ready: bool
    no_active_session: bool
    camera_ready: bool
    controller_required: bool
    controller_ready: bool
    blockers: list[str]
