import sqlite3

from app.db.transaction import transaction
from app.errors import ConflictError, ResourceNotFoundError
from app.repositories.employee_repository import EmployeeRepository
from app.schemas.employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate
from app.time_utils import utc_now_iso


class EmployeeService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.repository = EmployeeRepository(connection)

    def create(self, payload: EmployeeCreate) -> EmployeeResponse:
        if self.repository.find_by_number(payload.employee_number) is not None:
            raise ConflictError(
                f"Employee number {payload.employee_number} already exists"
            )

        try:
            with transaction(self.connection):
                record = self.repository.create(
                    employee_number=payload.employee_number,
                    name=payload.name,
                    sewing_line=payload.sewing_line,
                    timestamp=utc_now_iso(),
                )
        except sqlite3.IntegrityError as error:
            raise ConflictError(
                f"Employee number {payload.employee_number} already exists"
            ) from error

        return EmployeeResponse.model_validate(record)

    def get(self, employee_id: int) -> EmployeeResponse:
        record = self.repository.find_by_id(employee_id)
        if record is None:
            raise ResourceNotFoundError(f"Employee {employee_id} was not found")
        return EmployeeResponse.model_validate(record)

    def list(self, *, include_inactive: bool) -> list[EmployeeResponse]:
        return [
            EmployeeResponse.model_validate(record)
            for record in self.repository.list(include_inactive=include_inactive)
        ]

    def update(self, employee_id: int, payload: EmployeeUpdate) -> EmployeeResponse:
        if self.repository.find_by_id(employee_id) is None:
            raise ResourceNotFoundError(f"Employee {employee_id} was not found")

        changes = payload.model_dump(exclude_unset=True)
        if "is_active" in changes:
            changes["is_active"] = int(bool(changes["is_active"]))
        changes["updated_at"] = utc_now_iso()

        with transaction(self.connection):
            record = self.repository.update(employee_id, changes)

        return EmployeeResponse.model_validate(record)
