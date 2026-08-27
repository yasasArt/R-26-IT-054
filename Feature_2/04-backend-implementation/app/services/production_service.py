"""Transactional garment confirmation and live-metric rules."""

import sqlite3
from datetime import datetime

from app.db.transaction import transaction
from app.errors import ConflictError, ResourceNotFoundError
from app.repositories.piece_repository import PieceRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.piece_event import (
    EventSource,
    PieceConfirmationResponse,
    PieceEventResponse,
    ProductionSummaryResponse,
)
from app.schemas.session import SessionResponse
from app.time_utils import parse_utc, to_utc_iso, utc_now_iso


class ProductionService:
    """Keep event insertion and all derived session totals in one transaction."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        minimum_piece_gap_seconds: float,
    ) -> None:
        self.connection = connection
        self.minimum_piece_gap_seconds = minimum_piece_gap_seconds
        self.sessions = SessionRepository(connection)
        self.pieces = PieceRepository(connection)

    def _require_session(self, session_id: int) -> dict:
        session = self.sessions.find_by_id(session_id)
        if session is None:
            raise ResourceNotFoundError(f"Session {session_id} was not found")
        return session

    @staticmethod
    def _require_counting_allowed(session: dict) -> None:
        if session["status"] != "ACTIVE":
            raise ConflictError("Garments can only be confirmed for an active session")
        if session["operator_mode"] != "NORMAL":
            raise ConflictError("Garments cannot be confirmed during rework or downtime")

    @staticmethod
    def _summary_from(session: dict, aggregate: dict) -> ProductionSummaryResponse:
        total = int(aggregate["total_pieces"])
        target = int(session["target_pieces"])
        average = aggregate["average_cycle_seconds"]
        return ProductionSummaryResponse(
            session_id=int(session["id"]),
            status=session["status"],
            operator_mode=session["operator_mode"],
            target_pieces=target,
            total_pieces=total,
            remaining_pieces=max(0, target - total),
            achievement_percent=round((total / target) * 100, 2),
            average_cycle_seconds=(round(float(average), 3) if average is not None else None),
            latest_piece_at=aggregate["latest_piece_at"],
        )

    def mark_first_sewing_started(
        self,
        session_id: int,
        started_at: datetime,
    ) -> SessionResponse:
        """Latch the first classifier sewing transition exactly once."""

        started_at_text = to_utc_iso(started_at)
        with transaction(self.connection):
            session = self._require_session(session_id)
            self._require_counting_allowed(session)

            # Repeated workstation/classifier signals must not restart cycle one.
            if session["first_sewing_started_at"] is not None:
                return SessionResponse.model_validate(session)

            if parse_utc(started_at_text) < parse_utc(session["started_at"]):
                raise ConflictError("First sewing cannot start before the session")

            session = self.sessions.set_first_sewing_started_if_missing(
                session_id,
                started_at_text,
            )

        return SessionResponse.model_validate(session)

    def _confirmation_for_existing(
        self,
        session: dict,
        event: dict,
    ) -> PieceConfirmationResponse:
        aggregate = self.pieces.aggregate(int(session["id"]))
        return PieceConfirmationResponse(
            event=PieceEventResponse.model_validate(event),
            summary=self._summary_from(session, aggregate),
            duplicate=True,
        )

    def confirm_piece(
        self,
        session_id: int,
        *,
        event_key: str,
        completed_at: datetime,
        confidence: float | None,
        event_source: EventSource,
    ) -> PieceConfirmationResponse:
        """Confirm one garment once and atomically refresh all live metrics."""

        completed_at_text = to_utc_iso(completed_at)

        try:
            with transaction(self.connection):
                session = self._require_session(session_id)

                # An identical delivery is a successful replay, not another piece.
                existing = self.pieces.find_by_event_key(session_id, event_key)
                if existing is not None:
                    return self._confirmation_for_existing(session, existing)

                self._require_counting_allowed(session)
                first_start = session["first_sewing_started_at"]
                if first_start is None:
                    raise ConflictError(
                        "Record the first sewing transition before confirming a garment"
                    )

                previous = self.pieces.latest_for_session(session_id)
                cycle_start_text = (
                    previous["completed_at"] if previous is not None else first_start
                )
                cycle_seconds = (
                    parse_utc(completed_at_text) - parse_utc(cycle_start_text)
                ).total_seconds()

                if cycle_seconds <= 0:
                    raise ConflictError("Piece completion must occur after its cycle start")
                if cycle_seconds < self.minimum_piece_gap_seconds:
                    raise ConflictError(
                        "Piece completion is too close to the previous confirmation; "
                        "the event was rejected as a probable duplicate"
                    )

                created_at = utc_now_iso()
                event = self.pieces.insert(
                    session_id=session_id,
                    employee_id=int(session["employee_id"]),
                    piece_number=self.pieces.next_piece_number(session_id),
                    event_key=event_key,
                    sewing_started_at=cycle_start_text,
                    cycle_seconds=round(cycle_seconds, 3),
                    confidence=confidence,
                    event_source=event_source.value,
                    completed_at=completed_at_text,
                    created_at=created_at,
                )

                aggregate = self.pieces.aggregate(session_id)
                average = aggregate["average_cycle_seconds"]
                session = self.sessions.update_production_summary(
                    session_id,
                    total_pieces=int(aggregate["total_pieces"]),
                    average_cycle_seconds=(
                        round(float(average), 3) if average is not None else None
                    ),
                    timestamp=created_at,
                )
                summary = self._summary_from(session, aggregate)
        except sqlite3.IntegrityError:
            # A concurrent replay may win the unique-key insert race.
            existing = self.pieces.find_by_event_key(session_id, event_key)
            if existing is not None:
                return self._confirmation_for_existing(
                    self._require_session(session_id),
                    existing,
                )
            raise

        return PieceConfirmationResponse(
            event=PieceEventResponse.model_validate(event),
            summary=summary,
            duplicate=False,
        )

    def list_events(self, session_id: int) -> list[PieceEventResponse]:
        self._require_session(session_id)
        return [
            PieceEventResponse.model_validate(event)
            for event in self.pieces.list_for_session(session_id)
        ]

    def summary(self, session_id: int) -> ProductionSummaryResponse:
        session = self._require_session(session_id)
        return self._summary_from(session, self.pieces.aggregate(session_id))
