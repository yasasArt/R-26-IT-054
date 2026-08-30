"""Contracts for capture sources, runtime status and validation-video uploads."""

from datetime import datetime
from enum import StrEnum # type: ignore

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.vision.probability_smoother import TemporalState


class VisionSourceType(StrEnum):
    CAMERA = "CAMERA"
    VIDEO = "VIDEO"


class VisionRuntimeState(StrEnum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    WAITING_FOR_PREVIEW = "WAITING_FOR_PREVIEW"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class WorkstationState(StrEnum):
    SEARCHING = "SEARCHING"
    LATCHED = "LATCHED"
    PAUSED = "PAUSED"


class VisionStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: VisionSourceType
    camera_index: int | None = Field(default=None, ge=0, le=128)
    video_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[a-f0-9-]+\.(mp4|mov|avi|mkv|m4v)$",
    )

    @model_validator(mode="after")
    def validate_source_fields(self) -> "VisionStartRequest":
        if self.source_type == VisionSourceType.CAMERA and self.video_id is not None:
            raise ValueError("video_id cannot be used with a camera source")
        if self.source_type == VisionSourceType.VIDEO and self.video_id is None:
            raise ValueError("video_id is required for a video source")
        if self.source_type == VisionSourceType.VIDEO and self.camera_index is not None:
            raise ValueError("camera_index cannot be used with a video source")
        return self


class VisionRuntimeStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: VisionRuntimeState
    session_id: int | None = None
    source_type: VisionSourceType | None = None
    source_label: str | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    preview_ready: bool = False
    preview_subscribers: int = 0
    workstation_state: WorkstationState = WorkstationState.SEARCHING # type: ignore
    workstation_available: bool = False
    workstation_failed_rechecks: int = 0
    stable_state: TemporalState = TemporalState.UNCERTAIN # type: ignore
    idle_rearmed: bool = False
    last_probabilities: dict[str, float] | None = None
    processed_frames: int = 0
    inference_count: int = 0
    confirmed_pieces: int = 0
    stop_reason: str | None = None
    last_error: str | None = None


class VideoUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_id: str
    original_name: str
    size_bytes: int
