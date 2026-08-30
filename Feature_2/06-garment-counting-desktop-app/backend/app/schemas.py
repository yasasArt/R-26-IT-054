from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SessionMode = Literal["PRODUCTION", "VALIDATION"]
OperatorMode = Literal["NORMAL", "REWORK", "DOWNTIME"]
IoTEventType = Literal["REWORK", "DOWNTIME", "RESET", "DISCONNECTED", "RECONNECTED"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EmployeeCreate(StrictModel):
    employee_code: str = Field(min_length=2, max_length=30)
    full_name: str = Field(min_length=2, max_length=100)
    sewing_line: str = Field(min_length=1, max_length=60)


class EmployeeUpdate(StrictModel):
    employee_code: str = Field(min_length=2, max_length=30)
    full_name: str = Field(min_length=2, max_length=100)
    sewing_line: str = Field(min_length=1, max_length=60)
    active: bool = True


class DeviceConfigurationUpdate(StrictModel):
    camera_id: str | None = Field(default=None, max_length=255)
    camera_label: str | None = Field(default=None, max_length=160)
    camera_tested: bool = False
    iot_mode: Literal["NOT_CONFIGURED", "REAL", "SIMULATED"] = "NOT_CONFIGURED"
    iot_device_name: str | None = Field(default=None, max_length=160)
    iot_device_id: str | None = Field(default=None, max_length=255)
    simulation_approved: bool = False

    @field_validator("camera_id", "camera_label", "iot_device_name", "iot_device_id")
    @classmethod
    def blank_is_none(cls, value: str | None) -> str | None:
        return value or None


class IoTConnectionUpdate(StrictModel):
    device_id: str = Field(min_length=1, max_length=255)
    device_name: str = Field(min_length=1, max_length=160)
    connected: bool
    notifications_active: bool = False
    reason: str | None = Field(default=None, max_length=160)


class SessionCreate(StrictModel):
    employee_id: int = Field(gt=0)
    target_pieces: int = Field(gt=0, le=100000)
    workstation_id: str = Field(default="WS-01", min_length=1, max_length=60)
    session_mode: SessionMode = "PRODUCTION"


class SessionDataDelete(StrictModel):
    confirmation: Literal["DELETE SESSION DATA"]


class SewingStart(StrictModel):
    started_at: datetime | None = None


class CameraTest(StrictModel):
    camera_id: str = Field(min_length=1, max_length=20, pattern=r"^\d+$")


class VisionStart(StrictModel):
    session_id: int = Field(gt=0)
    source_type: Literal["camera", "video"] = "camera"
    video_path: str | None = Field(default=None, max_length=4096)


class PieceCreate(StrictModel):
    sewing_started_at: datetime | None = None
    completed_at: datetime | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    event_source: Literal["VISION", "VALIDATION"] = "VISION"


class IoTEventCreate(StrictModel):
    session_id: int | None = Field(default=None, gt=0)
    event_type: IoTEventType
    event_source: Literal["HARDWARE", "VALIDATION"] = "HARDWARE"
    occurred_at: datetime | None = None
    device_name: str | None = Field(default=None, max_length=160)
    payload: dict[str, Any] | None = None
