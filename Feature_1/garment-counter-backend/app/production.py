from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import HTTPException

from app.database import transaction
from app.schemas import PieceCreate
from app.time_utils import format_utc, parse_utc, utc_now


def persist_piece_event(
    connection: sqlite3.Connection, session_id: int, payload: PieceCreate
) -> dict[str, Any]:
    """Shared, transactional policy boundary for manual validation and real inference."""

    with transaction(connection):
        session = connection.execute(
            "SELECT * FROM production_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        configuration = connection.execute(
            "SELECT * FROM device_configuration WHERE id = 1"
        ).fetchone()

        if session is None:
            raise HTTPException(status_code=404, detail="The requested production session was not found.")
        if configuration is None or session["status"] != "ACTIVE":
            raise HTTPException(status_code=409, detail="The selected session is no longer active.")
        if session["operator_mode"] != "NORMAL":
            raise HTTPException(status_code=409, detail="Counting is paused during rework or downtime.")
        if not configuration["iot_connected"] or not configuration["iot_notifications_active"]:
            raise HTTPException(status_code=409, detail="Counting is paused because the controller is disconnected.")
        if session["session_mode"] == "PRODUCTION" and payload.event_source != "VISION":
            raise HTTPException(status_code=409, detail="Production sessions cannot accept simulated count events.")
        if session["session_mode"] == "VALIDATION" and payload.event_source != "VALIDATION":
            raise HTTPException(status_code=409, detail="Validation count events must be explicitly identified.")

        completed_at = parse_utc(format_utc(payload.completed_at or utc_now()))
        previous = connection.execute(
            "SELECT * FROM piece_events WHERE session_id = ? ORDER BY piece_number DESC LIMIT 1",
            (session_id,),
        ).fetchone()

        if payload.sewing_started_at is not None:
            cycle_reference = parse_utc(format_utc(payload.sewing_started_at))
        elif previous is not None:
            cycle_reference = parse_utc(previous["completed_at"])
        elif session["first_sewing_started_at"]:
            cycle_reference = parse_utc(session["first_sewing_started_at"])
        else:
            cycle_reference = parse_utc(session["started_at"])

        cycle_seconds = round((completed_at - cycle_reference).total_seconds(), 3)
        if cycle_seconds < 0:
            raise HTTPException(status_code=422, detail="The piece completion time cannot precede its cycle start.")

        piece_number = int(session["total_pieces"]) + 1
        timestamp = format_utc(utc_now())
        cursor = connection.execute(
            "INSERT INTO piece_events(session_id, piece_number, cycle_seconds, sewing_started_at, "
            "completed_at, confidence, event_source, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                piece_number,
                cycle_seconds,
                format_utc(payload.sewing_started_at)
                if payload.sewing_started_at
                else session["first_sewing_started_at"],
                format_utc(completed_at),
                payload.confidence,
                payload.event_source,
                timestamp,
            ),
        )
        average_cycle = connection.execute(
            "SELECT AVG(cycle_seconds) FROM piece_events WHERE session_id = ?", (session_id,)
        ).fetchone()[0]
        connection.execute(
            "UPDATE production_sessions SET total_pieces = ?, average_cycle_seconds = ? WHERE id = ?",
            (piece_number, round(float(average_cycle), 3), session_id),
        )
        event = connection.execute(
            "SELECT * FROM piece_events WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()

    assert event is not None
    return dict(event)
