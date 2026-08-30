from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import datetime
from typing import Any

from app.time_utils import format_utc, parse_utc, utc_now


def calculate_event_intervals(
    events: list[dict[str, Any]], session_end: str | None = None
) -> dict[str, Any]:
    mode_started: datetime | None = None
    active_mode = "NORMAL"
    disconnected_at: datetime | None = None
    rework_seconds = 0.0
    downtime_seconds = 0.0
    disconnected_seconds = 0.0
    rework_count = 0
    downtime_count = 0
    disconnect_count = 0

    for event in events:
        event_time = parse_utc(event["occurred_at"])
        event_type = event["event_type"]

        if event_type in {"REWORK", "DOWNTIME", "RESET"}:
            if mode_started is not None and active_mode == "REWORK":
                rework_seconds += max(0.0, (event_time - mode_started).total_seconds())
            elif mode_started is not None and active_mode == "DOWNTIME":
                downtime_seconds += max(0.0, (event_time - mode_started).total_seconds())

            if event_type == "REWORK":
                rework_count += 1
                active_mode = "REWORK"
                mode_started = event_time
            elif event_type == "DOWNTIME":
                downtime_count += 1
                active_mode = "DOWNTIME"
                mode_started = event_time
            else:
                active_mode = "NORMAL"
                mode_started = None

        if event_type == "DISCONNECTED" and disconnected_at is None:
            disconnect_count += 1
            disconnected_at = event_time
        elif event_type == "RECONNECTED" and disconnected_at is not None:
            disconnected_seconds += max(0.0, (event_time - disconnected_at).total_seconds())
            disconnected_at = None

    if session_end:
        end_time = parse_utc(session_end)

        if mode_started is not None and active_mode == "REWORK":
            rework_seconds += max(0.0, (end_time - mode_started).total_seconds())
        elif mode_started is not None and active_mode == "DOWNTIME":
            downtime_seconds += max(0.0, (end_time - mode_started).total_seconds())

        if disconnected_at is not None:
            disconnected_seconds += max(0.0, (end_time - disconnected_at).total_seconds())

    return {
        "rework_count": rework_count,
        "downtime_count": downtime_count,
        "disconnect_count": disconnect_count,
        "rework_seconds": round(rework_seconds, 3),
        "downtime_seconds": round(downtime_seconds, 3),
        "disconnected_seconds": round(disconnected_seconds, 3),
    }


def build_analytics(
    connection: sqlite3.Connection,
    *,
    employee_id: int | None = None,
    session_id: int | None = None,
    sewing_line: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    session_mode: str | None = None,
) -> dict[str, Any]:
    conditions: list[str] = []
    values: list[Any] = []

    if employee_id is not None:
        conditions.append("employee_id = ?")
        values.append(employee_id)
    if session_id is not None:
        conditions.append("id = ?")
        values.append(session_id)
    if sewing_line:
        conditions.append("sewing_line = ?")
        values.append(sewing_line)
    if start_date:
        conditions.append("substr(started_at, 1, 10) >= ?")
        values.append(start_date)
    if end_date:
        conditions.append("substr(started_at, 1, 10) <= ?")
        values.append(end_date)
    if session_mode:
        conditions.append("session_mode = ?")
        values.append(session_mode)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sessions = [
        dict(row)
        for row in connection.execute(
            f"SELECT * FROM production_sessions {where_clause} ORDER BY started_at DESC, id DESC",
            values,
        ).fetchall()
    ]

    if not sessions:
        return {
            "generated_at": format_utc(utc_now()),
            "filters": {
                "employee_id": employee_id,
                "session_id": session_id,
                "sewing_line": sewing_line,
                "start_date": start_date,
                "end_date": end_date,
                "session_mode": session_mode,
            },
            "summary": {
                "session_count": 0,
                "completed_session_count": 0,
                "employee_count": 0,
                "total_pieces": 0,
                "target_pieces": 0,
                "achievement_percent": 0.0,
                "average_cycle_seconds": None,
                "rework_count": 0,
                "downtime_count": 0,
                "disconnect_count": 0,
                "rework_seconds": 0.0,
                "downtime_seconds": 0.0,
                "disconnected_seconds": 0.0,
            },
            "sessions": [],
            "piece_events": [],
            "iot_events": [],
            "employees": [],
        }

    session_ids = [session["id"] for session in sessions]
    placeholders = ",".join("?" for _ in session_ids)
    piece_events = [
        dict(row)
        for row in connection.execute(
            f"SELECT * FROM piece_events WHERE session_id IN ({placeholders}) "
            "ORDER BY session_id, piece_number",
            session_ids,
        ).fetchall()
    ]
    iot_events = [
        dict(row)
        for row in connection.execute(
            f"SELECT * FROM iot_events WHERE session_id IN ({placeholders}) "
            "ORDER BY session_id, occurred_at, id",
            session_ids,
        ).fetchall()
    ]

    events_by_session: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for event in iot_events:
        events_by_session[int(event["session_id"])].append(event)

    employee_totals: dict[int, dict[str, Any]] = {}

    for session in sessions:
        metrics = calculate_event_intervals(
            events_by_session.get(session["id"], []),
            session.get("ended_at") or format_utc(utc_now()),
        )
        target_pieces = int(session["target_pieces"])
        produced_pieces = int(session["total_pieces"])
        session.update(metrics)
        session["achievement_percent"] = round(produced_pieces / target_pieces * 100, 2)
        session["remaining_pieces"] = max(0, target_pieces - produced_pieces)
        session["simulated_iot"] = bool(session["simulated_iot"])

        employee = employee_totals.setdefault(
            session["employee_id"],
            {
                "employee_id": session["employee_id"],
                "employee_code": session["employee_code"],
                "employee_name": session["employee_name"],
                "sewing_line": session["sewing_line"],
                "session_count": 0,
                "total_pieces": 0,
                "target_pieces": 0,
                "rework_count": 0,
                "downtime_count": 0,
                "rework_seconds": 0.0,
                "downtime_seconds": 0.0,
            },
        )
        employee["session_count"] += 1
        employee["total_pieces"] += produced_pieces
        employee["target_pieces"] += target_pieces
        employee["rework_count"] += metrics["rework_count"]
        employee["downtime_count"] += metrics["downtime_count"]
        employee["rework_seconds"] += metrics["rework_seconds"]
        employee["downtime_seconds"] += metrics["downtime_seconds"]

    for employee in employee_totals.values():
        employee["achievement_percent"] = round(
            employee["total_pieces"] / employee["target_pieces"] * 100, 2
        )
        employee["rework_seconds"] = round(employee["rework_seconds"], 3)
        employee["downtime_seconds"] = round(employee["downtime_seconds"], 3)

    total_pieces = sum(int(session["total_pieces"]) for session in sessions)
    target_pieces = sum(int(session["target_pieces"]) for session in sessions)
    cycle_values = [float(event["cycle_seconds"]) for event in piece_events]

    return {
        "generated_at": format_utc(utc_now()),
        "filters": {
            "employee_id": employee_id,
            "session_id": session_id,
            "sewing_line": sewing_line,
            "start_date": start_date,
            "end_date": end_date,
            "session_mode": session_mode,
        },
        "summary": {
            "session_count": len(sessions),
            "completed_session_count": sum(session["status"] == "COMPLETED" for session in sessions),
            "employee_count": len(employee_totals),
            "total_pieces": total_pieces,
            "target_pieces": target_pieces,
            "achievement_percent": round(total_pieces / target_pieces * 100, 2)
            if target_pieces
            else 0.0,
            "average_cycle_seconds": round(sum(cycle_values) / len(cycle_values), 3)
            if cycle_values
            else None,
            "rework_count": sum(session["rework_count"] for session in sessions),
            "downtime_count": sum(session["downtime_count"] for session in sessions),
            "disconnect_count": sum(session["disconnect_count"] for session in sessions),
            "rework_seconds": round(sum(session["rework_seconds"] for session in sessions), 3),
            "downtime_seconds": round(sum(session["downtime_seconds"] for session in sessions), 3),
            "disconnected_seconds": round(
                sum(session["disconnected_seconds"] for session in sessions), 3
            ),
        },
        "sessions": sessions,
        "piece_events": piece_events,
        "iot_events": iot_events,
        "employees": sorted(
            employee_totals.values(), key=lambda employee: str(employee["employee_name"]).casefold()
        ),
    }
