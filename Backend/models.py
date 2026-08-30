from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field





class BreakWindow(BaseModel):
    name: str
    start_time: str  # "HH:MM", 24-hour, factory-local time
    duration_minutes: float


# The four classes the detection model is trained on - keys match style_name
# exactly as the CV pipeline writes it (garments.style_name), so category
# targets can be joined against packed counts with a plain equality filter.
class CategoryTargets(BaseModel):
    SHIRT: int = 0
    T_SHIRT: int = 0
    TROUSER: int = 0
    SHORT: int = 0


class Settings(BaseModel):
    target_pieces: int
    category_targets: CategoryTargets = Field(default_factory=CategoryTargets)
    start_date: date
    due_date: date
    work_start_time: str  # "HH:MM"
    work_end_time: str  # "HH:MM"
    breaks: List[BreakWindow] = Field(default_factory=list)


class DowntimeEvent(BaseModel):
    type: Literal["breakdown", "power_failure"]
    start: datetime
    end: datetime
    reason: Optional[str] = None


class CameraDevice(BaseModel):
    camera_index: int
    camera_label: str
