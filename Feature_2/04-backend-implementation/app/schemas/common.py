from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):

    model_config = ConfigDict(extra="forbid")

    status: Literal["starting", "ok"]
    service: str
    version: str
    environment: Literal["development", "test", "production"]
    ready: bool


class DatabaseHealthResponse(BaseModel):

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    schema_version: int
    foreign_keys: bool
    journal_mode: str
    busy_timeout_ms: int
