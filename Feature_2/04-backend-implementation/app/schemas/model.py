from enum import StrEnum # type: ignore

from pydantic import BaseModel, ConfigDict


class ModelLoadState(StrEnum):
    NOT_LOADED = "NOT_LOADED"
    READY = "READY"
    MISSING = "MISSING"
    INVALID = "INVALID"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"


class ModelComponentStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    state: ModelLoadState
    path: str
    loaded: bool
    message: str


class ModelRegistryStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: bool
    device: str
    classifier: ModelComponentStatus
    label_mapping: ModelComponentStatus
    workstation_detector: ModelComponentStatus
