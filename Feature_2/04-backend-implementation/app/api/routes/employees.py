from fastapi import APIRouter, Query, status

from app.api.dependencies import DatabaseDependency
from app.schemas.employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate
from app.services.employee_service import EmployeeService

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: EmployeeCreate,
    connection: DatabaseDependency,
) -> EmployeeResponse:
    return EmployeeService(connection).create(payload)


@router.get("", response_model=list[EmployeeResponse])
def list_employees(
    connection: DatabaseDependency,
    include_inactive: bool = Query(default=False),
) -> list[EmployeeResponse]:
    return EmployeeService(connection).list(include_inactive=include_inactive)


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(
    employee_id: int,
    connection: DatabaseDependency,
) -> EmployeeResponse:
    return EmployeeService(connection).get(employee_id)


@router.patch("/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    payload: EmployeeUpdate,
    connection: DatabaseDependency,
) -> EmployeeResponse:
    return EmployeeService(connection).update(employee_id, payload)
