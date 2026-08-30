from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.api.dependencies import DatabaseDependency
from app.errors import InvalidOperationError
from app.schemas.analytics import AnalyticsFilters, AnalyticsResponse
from app.schemas.session import SessionMode, SessionStatus
from app.services.analytics_service import AnalyticsService
from app.services.excel_service import ExcelService

router = APIRouter(prefix="/analytics", tags=["Analytics and reports"])


def get_analytics_filters(
    session_id: Annotated[int | None, Query(ge=1)] = None,
    employee_id: Annotated[int | None, Query(ge=1)] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    session_status: Annotated[SessionStatus | None, Query()] = None,
    session_mode: Annotated[SessionMode | None, Query()] = None,
) -> AnalyticsFilters:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise InvalidOperationError("date_from cannot be after date_to")
    return AnalyticsFilters(
        session_id=session_id,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
        session_status=session_status,
        session_mode=session_mode,
    )


AnalyticsFiltersDependency = Annotated[AnalyticsFilters, Depends(get_analytics_filters)]


@router.get("", response_model=AnalyticsResponse)
def analytics_report(
    connection: DatabaseDependency,
    filters: AnalyticsFiltersDependency,
) -> AnalyticsResponse:
    return AnalyticsService(connection).report(filters)


@router.get("/export")
def export_analytics(
    connection: DatabaseDependency,
    filters: AnalyticsFiltersDependency,
) -> Response:
    report = AnalyticsService(connection).report(filters)
    workbook = ExcelService(report).build()
    timestamp = report.generated_at.strftime("%Y%m%d_%H%M%S")
    filename = f"garment_counter_analytics_{timestamp}.xlsx"
    return Response(
        content=workbook,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

