"""Device-configuration request and response contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DeviceConfigurationUpdate(BaseModel):
    """Editable device selections.

    Tested/connected flags are intentionally absent. Later trusted camera and
    Bluetooth handlers will update those values after physical verification.
    """

    model_config = ConfigDict(extra="forbid")

    camera_index: int | None = Field(default=None, ge=0, le=64)
    camera_label: str | None = Field(default=None, max_length=160)
    controller_device_id: str | None = Field(default=None, max_length=200)
    controller_name: str | None = Field(default=None, max_length=160)

    @field_validator("camera_label", "controller_device_id", "controller_name")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @model_validator(mode="after")
    def require_a_supplied_field(self) -> "DeviceConfigurationUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one configuration field")
        return self


class DeviceConfigurationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    camera_index: int | None
    camera_label: str | None
    camera_tested: bool
    controller_device_id: str | None
    controller_name: str | None
    controller_connected: bool
    created_at: datetime
    updated_at: datetime
