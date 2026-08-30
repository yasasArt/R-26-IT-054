import sqlite3
from datetime import UTC, datetime # type: ignore

from app.db.transaction import transaction
from app.errors import ConflictError, ResourceNotFoundError
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.analytics import (
    ActivityAnalytics,
    AnalyticsFilters,
    AnalyticsResponse,
    ManagementSummary,
    OperatorEventAnalytics,
    PieceCycleAnalytics,
    SessionAnalytics,
    SessionHistoryDeleteResponse,
)
from app.schemas.session import OperatorMode
from app.time_utils import parse_utc


class AnalyticsService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.analytics = AnalyticsRepository(connection)
        self.sessions = SessionRepository(connection)

    @staticmethod
    def _operator_activity(
        events: list[dict],
        *,
        through: datetime,
    ) -> tuple[ActivityAnalytics, ActivityAnalytics, list[OperatorEventAnalytics]]:
        counts = {OperatorMode.REWORK: 0, OperatorMode.DOWNTIME: 0}
        durations = {OperatorMode.REWORK: 0.0, OperatorMode.DOWNTIME: 0.0}
        open_mode: OperatorMode | None = None
        opened_at: datetime | None = None
        event_rows: list[OperatorEventAnalytics] = []

        for event in events:
            event_at = parse_utc(event["occurred_at"])
            if event_at > through:
                break
            before = OperatorMode(event["mode_before"])
            after = OperatorMode(event["mode_after"])
            closed_duration: float | None = None

            if before is OperatorMode.NORMAL and after in counts:
                counts[after] += 1
                open_mode = after
                opened_at = event_at
            elif after is OperatorMode.NORMAL and open_mode is not None:
                assert opened_at is not None
                closed_duration = max(0.0, (event_at - opened_at).total_seconds())
                durations[open_mode] += closed_duration
                open_mode = None
                opened_at = None

            event_rows.append(
                OperatorEventAnalytics(
                    event_id=event["id"],
                    event_type=event["event_type"],
                    mode_before=before,
                    mode_after=after,
                    device_name=event["device_name"],
                    event_source=event["event_source"],
                    occurred_at=event_at,
                    closed_mode_duration_seconds=(
                        round(closed_duration, 3)
                        if closed_duration is not None
                        else None
                    ),
                )
            )

        if open_mode is not None and opened_at is not None:
            durations[open_mode] += max(0.0, (through - opened_at).total_seconds())

        return (
            ActivityAnalytics(
                count=counts[OperatorMode.REWORK],
                duration_seconds=round(durations[OperatorMode.REWORK], 3),
            ),
            ActivityAnalytics(
                count=counts[OperatorMode.DOWNTIME],
                duration_seconds=round(durations[OperatorMode.DOWNTIME], 3),
            ),
            event_rows,
        )

    def _session_report(self, session: dict, generated_at: datetime) -> SessionAnalytics:
        session_id = int(session["id"])
        pieces = self.analytics.list_piece_events(session_id)
        iot_events = self.analytics.list_iot_events(session_id)
        ended_at = parse_utc(session["ended_at"]) if session["ended_at"] else None
        through = ended_at or generated_at
        rework, downtime, operator_events = self._operator_activity(
            iot_events,
            through=through,
        )

        piece_rows = [
            PieceCycleAnalytics(
                event_id=piece["id"],
                piece_number=piece["piece_number"],
                cycle_seconds=round(float(piece["cycle_seconds"]), 3),
                confidence=piece["confidence"],
                event_source=piece["event_source"],
                sewing_started_at=(
                    parse_utc(piece["sewing_started_at"])
                    if piece["sewing_started_at"]
                    else None
                ),
                completed_at=parse_utc(piece["completed_at"]),
            )
            for piece in pieces
        ]
        confirmed = len(piece_rows)
        target = int(session["target_pieces"])
        average = (
            round(sum(piece.cycle_seconds for piece in piece_rows) / confirmed, 3)
            if confirmed
            else None
        )

        return SessionAnalytics(
            session_id=session_id,
            employee_id=session["employee_id"],
            employee_number=session["employee_number_snapshot"],
            employee_name=session["employee_name_snapshot"],
            sewing_line=session["sewing_line_snapshot"],
            session_mode=session["session_mode"],
            session_status=session["status"],
            operator_mode=session["operator_mode"],
            started_at=parse_utc(session["started_at"]),
            ended_at=ended_at,
            target_pieces=target,
            confirmed_pieces=confirmed,
            remaining_pieces=max(0, target - confirmed),
            achievement_percent=round((confirmed / target) * 100, 2),
            average_cycle_seconds=average,
            individual_cycle_times=piece_rows,
            rework=rework,
            downtime=downtime,
            operator_events=operator_events,
        )

    @staticmethod
    def _management_summary(reports: list[SessionAnalytics]) -> ManagementSummary:
        all_cycles = [
            piece.cycle_seconds
            for report in reports
            for piece in report.individual_cycle_times
        ]
        target = sum(report.target_pieces for report in reports)
        confirmed = sum(report.confirmed_pieces for report in reports)

        return ManagementSummary(
            total_sessions=len(reports),
            unique_employees=len({report.employee_id for report in reports}),
            active_sessions=sum(
                report.session_status.value == "ACTIVE" for report in reports
            ),
            completed_sessions=sum(
                report.session_status.value == "COMPLETED" for report in reports
            ),
            cancelled_sessions=sum(
                report.session_status.value == "CANCELLED" for report in reports
            ),
            target_pieces=target,
            confirmed_pieces=confirmed,
            remaining_pieces=sum(report.remaining_pieces for report in reports),
            achievement_percent=(
                round((confirmed / target) * 100, 2) if target else 0.0
            ),
            average_cycle_seconds=(
                round(sum(all_cycles) / len(all_cycles), 3) if all_cycles else None
            ),
            rework_count=sum(report.rework.count for report in reports),
            rework_duration_seconds=round(
                sum(report.rework.duration_seconds for report in reports),
                3,
            ),
            downtime_count=sum(report.downtime.count for report in reports),
            downtime_duration_seconds=round(
                sum(report.downtime.duration_seconds for report in reports),
                3,
            ),
        )

    def report(self, filters: AnalyticsFilters) -> AnalyticsResponse:
        generated_at = datetime.now(UTC)
        reports = [
            self._session_report(session, generated_at)
            for session in self.analytics.list_sessions(filters)
        ]
        return AnalyticsResponse(
            generated_at=generated_at,
            filters=filters,
            summary=self._management_summary(reports),
            sessions=reports,
        )

    def delete_session_history(self, session_id: int) -> SessionHistoryDeleteResponse:
        with transaction(self.connection):
            if self.sessions.find_active() is not None:
                raise ConflictError(
                    "Session history cannot be deleted while a production session is active"
                )

            session = self.sessions.find_by_id(session_id)
            if session is None:
                raise ResourceNotFoundError(f"Session {session_id} was not found")

            expected_pieces, expected_iot = self.analytics.child_counts(session_id)
            deleted_pieces = self.analytics.delete_piece_events(session_id)
            deleted_iot = self.analytics.delete_iot_events(session_id)
            deleted_sessions = self.analytics.delete_session(session_id)

            if (
                deleted_pieces != expected_pieces
                or deleted_iot != expected_iot
                or deleted_sessions != 1
            ):
                raise ConflictError("Session history changed during deletion")

        return SessionHistoryDeleteResponse(
            session_id=session_id,
            deleted_piece_events=deleted_pieces,
            deleted_iot_events=deleted_iot,
            deleted_sessions=deleted_sessions,
        )
