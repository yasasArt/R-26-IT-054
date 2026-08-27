from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

EmployeeNumber = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=40,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
    ),
]
EmployeeName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
SewingLine = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class EmployeeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_number: EmployeeNumber
    name: EmployeeName
    sewing_line: SewingLine

    @field_validator("employee_number")
    @classmethod
    def normalize_employee_number(cls, value: str) -> str:
        return value.upper()


class EmployeeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: EmployeeName | None = None
    sewing_line: SewingLine | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_at_least_one_non_null_change(self) -> "EmployeeUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one employee field to update")

        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    employee_number: str
    name: str
    sewing_line: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
