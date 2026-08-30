"""Idempotently add sample employees for local development."""

from app.config import get_settings
from app.db.connection import connect_database
from app.db.migrations import apply_migrations
from app.errors import ConflictError
from app.schemas.employee import EmployeeCreate
from app.services.employee_service import EmployeeService

SAMPLE_EMPLOYEES = (
    EmployeeCreate(employee_number="EMP-001", name="Sample Operator One", sewing_line="Line 1"),
    EmployeeCreate(employee_number="EMP-002", name="Sample Operator Two", sewing_line="Line 2"),
    EmployeeCreate(employee_number="EMP-003", name="Sample Operator Three", sewing_line="Line 3"),
)


def main() -> None:
    settings = get_settings()
    settings.ensure_directories()
    assert settings.database_path is not None

    connection = connect_database(settings.database_path)
    try:
        apply_migrations(connection)
        service = EmployeeService(connection)

        for payload in SAMPLE_EMPLOYEES:
            try:
                employee = service.create(payload)
                print(f"Created {employee.employee_number}: {employee.name}")
            except ConflictError:
                print(f"Skipped {payload.employee_number}: already exists")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
