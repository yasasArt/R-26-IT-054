from __future__ import annotations

from typing import Any, Mapping


CYCLE_STATUS_WITHIN = "WITHIN_ESTIMATE"
CYCLE_STATUS_OVER = "OVER_ESTIMATE"
CYCLE_STATUS_UNAVAILABLE = "NOT_CONFIGURED"


def cycle_status(cycle_seconds: float | None, estimated_cycle_time_sec: float | None) -> str:
    """Classify a measured cycle against the session's selected benchmark."""

    if cycle_seconds is None or estimated_cycle_time_sec is None:
        return CYCLE_STATUS_UNAVAILABLE
    return (
        CYCLE_STATUS_WITHIN
        if float(cycle_seconds) <= float(estimated_cycle_time_sec)
        else CYCLE_STATUS_OVER
    )


def enrich_piece_event(
    event: Mapping[str, Any],
    *,
    operation_type: str | None,
    estimated_cycle_time_sec: float | None,
) -> dict[str, Any]:
    result = dict(event)
    measured = float(result["cycle_seconds"])
    estimate = float(estimated_cycle_time_sec) if estimated_cycle_time_sec is not None else None
    result["operation_type"] = operation_type
    result["estimated_cycle_time_sec"] = estimate
    result["cycle_status"] = cycle_status(measured, estimate)
    result["cycle_difference_sec"] = round(measured - estimate, 3) if estimate is not None else None
    return result


def enrich_session_cycle_status(session: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(session)
    average = result.get("average_cycle_seconds")
    estimate = result.get("estimated_cycle_time_sec")
    result["average_cycle_status"] = cycle_status(average, estimate)
    result["average_cycle_difference_sec"] = (
        round(float(average) - float(estimate), 3)
        if average is not None and estimate is not None
        else None
    )
    return result
