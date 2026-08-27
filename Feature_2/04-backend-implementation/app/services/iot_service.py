"""Transactional operator-mode transitions and duration calculations."""

import sqlite3
from datetime import datetime

from app.db.transaction import transaction
from app.errors import ConflictError, InvalidOperationError, ResourceNotFoundError
from app.repositories.iot_repository import IoTRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.iot_event import (
    IoTEventResponse,
    IoTEventSource,
    IoTEventType,
    IoTSummaryResponse,
    IoTTransitionResponse,
    ModeDurationSummary,
)
from app.schemas.session import OperatorMode, SessionResponse
from app.time_utils import parse_utc, to_utc_iso, utc_now_iso

MODE_TRANSITIONS: dict[tuple[OperatorMode, IoTEventType], OperatorMode] = {
    (OperatorMode.NORMAL, IoTEventType.REWORK): OperatorMode.REWORK,
    (OperatorMode.NORMAL, IoTEventType.DOWNTIME): OperatorMode.DOWNTIME,
    (OperatorMode.REWORK, IoTEventType.RESET): OperatorMode.NORMAL,
    (OperatorMode.DOWNTIME, IoTEventType.RESET): OperatorMode.NORMAL,
}


class IoTService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.sessions = SessionRepository(connection)
        self.events = IoTRepository(connection)

    def _require_session(self, session_id: int) -> dict:
        session = self.sessions.find_by_id(session_id)
        if session is None:
            raise ResourceNotFoundError(f"Session {session_id} was not found")
        return session

    @staticmethod
    def _next_mode(current_mode: str, event_type: IoTEventType) -> OperatorMode:
        if event_type in {IoTEventType.CONNECTED, IoTEventType.DISCONNECTED}:
            raise InvalidOperationError(
                "Connection events are owned by the trusted Bluetooth integration"
            )

        current = OperatorMode(current_mode)
        next_mode = MODE_TRANSITIONS.get((current, event_type))
        if next_mode is None:
            if event_type is IoTEventType.RESET and current is OperatorMode.NORMAL:
                raise ConflictError("The operator is already in normal mode")
            raise ConflictError(
                f"Cannot apply {event_type.value} while operator mode is {current.value}"
            )
        return next_mode

    def _closed_duration(self, event: dict) -> float | None:
        if event["event_type"] != IoTEventType.RESET.value:
            return None
        previous = self.events.previous_for_event(event)
        if previous is None or previous["mode_after"] == OperatorMode.NORMAL.value:
            return None
        return round(
            (parse_utc(event["occurred_at"]) - parse_utc(previous["occurred_at"]))
            .total_seconds(),
            3,
        )

    def _transition_response(
        self,
        session: dict,
        event: dict,
        *,
        duplicate: bool,
    ) -> IoTTransitionResponse:
        return IoTTransitionResponse(
            event=IoTEventResponse.model_validate(event),
            session=SessionResponse.model_validate(session),
            duplicate=duplicate,
            closed_mode_duration_seconds=self._closed_duration(event),
        )

    def record_transition(
        self,
        session_id: int,
        *,
        event_key: str,
        event_type: IoTEventType,
        occurred_at: datetime,
        event_source: IoTEventSource,
        device_name: str | None = None,
        device_id: str | None = None,
    ) -> IoTTransitionResponse:
        """Store one valid transition and change the session in one transaction."""

        occurred_at_text = to_utc_iso(occurred_at)

        try:
            with transaction(self.connection):
                session = self._require_session(session_id)
                existing = self.events.find_by_event_key(session_id, event_key)
                if existing is not None:
                    return self._transition_response(
                        session,
                        existing,
                        duplicate=True,
                    )

                if session["status"] != "ACTIVE":
                    raise ConflictError(
                        "Operator events can only be recorded for an active session"
                    )
                if parse_utc(occurred_at_text) < parse_utc(session["started_at"]):
                    raise ConflictError("Operator event cannot occur before the session")

                latest = self.events.latest_for_session(session_id)
                if latest is not None and parse_utc(occurred_at_text) < parse_utc(
                    latest["occurred_at"]
                ):
                    raise ConflictError(
                        "Operator events must be recorded in chronological order"
                    )

                mode_before = OperatorMode(session["operator_mode"])
                mode_after = self._next_mode(session["operator_mode"], event_type)
                created_at = utc_now_iso()
                event = self.events.insert(
                    session_id=session_id,
                    employee_id=int(session["employee_id"]),
                    event_key=event_key,
                    event_type=event_type.value,
                    mode_before=mode_before.value,
                    mode_after=mode_after.value,
                    device_name=(
                        device_name
                        if device_name is not None
                        else session["controller_name_snapshot"]
                    ),
                    device_id=(
                        device_id
                        if device_id is not None
                        else session["controller_device_id_snapshot"]
                    ),
                    event_source=event_source.value,
                    occurred_at=occurred_at_text,
                    created_at=created_at,
                )
                updated_session = self.sessions.update_operator_mode(
                    session_id,
                    mode_before=mode_before.value,
                    mode_after=mode_after.value,
                    timestamp=created_at,
                )
                if updated_session is None:
                    raise ConflictError("The operator mode changed before this event")
        except sqlite3.IntegrityError:
            existing = self.events.find_by_event_key(session_id, event_key)
            if existing is not None:
                return self._transition_response(
                    self._require_session(session_id),
                    existing,
                    duplicate=True,
                )
            raise

        return self._transition_response(
            updated_session,
            event,
            duplicate=False,
        )

    def list_events(self, session_id: int) -> list[IoTEventResponse]:
        self._require_session(session_id)
        return [
            IoTEventResponse.model_validate(event)
            for event in self.events.list_for_session(session_id)
        ]

    def summary(
        self,
        session_id: int,
        *,
        calculated_through: datetime,
    ) -> IoTSummaryResponse:
        session = self._require_session(session_id)
        through = parse_utc(to_utc_iso(calculated_through))
        if through < parse_utc(session["started_at"]):
            raise InvalidOperationError(
                "The summary time cannot be before the session start"
            )
        events = self.events.list_for_session(session_id)

        counts = {OperatorMode.REWORK: 0, OperatorMode.DOWNTIME: 0}
        durations = {OperatorMode.REWORK: 0.0, OperatorMode.DOWNTIME: 0.0}
        open_mode: OperatorMode | None = None
        opened_at = None
        mode_at_through = OperatorMode.NORMAL

        for event in events:
            event_at = parse_utc(event["occurred_at"])
            if event_at > through:
                break

            after = OperatorMode(event["mode_after"])
            before = OperatorMode(event["mode_before"])
            mode_at_through = after
            if before is OperatorMode.NORMAL and after in counts:
                counts[after] += 1
                open_mode = after
                opened_at = event_at
            elif after is OperatorMode.NORMAL and open_mode is not None:
                durations[open_mode] += max(
                    0.0,
                    (event_at - opened_at).total_seconds(),
                )
                open_mode = None
                opened_at = None

        effective_through = through
        if session["ended_at"] is not None:
            effective_through = min(effective_through, parse_utc(session["ended_at"]))
        if open_mode is not None and opened_at is not None:
            durations[open_mode] += max(
                0.0,
                (effective_through - opened_at).total_seconds(),
            )

        return IoTSummaryResponse(
            session_id=session_id,
            current_mode=mode_at_through,
            rework=ModeDurationSummary(
                count=counts[OperatorMode.REWORK],
                duration_seconds=round(durations[OperatorMode.REWORK], 3),
            ),
            downtime=ModeDurationSummary(
                count=counts[OperatorMode.DOWNTIME],
                duration_seconds=round(durations[OperatorMode.DOWNTIME], 3),
            ),
            active_mode_started_at=opened_at,
            calculated_through=effective_through,
        )
