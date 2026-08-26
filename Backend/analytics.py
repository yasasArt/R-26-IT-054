import json
import math
from datetime import date, datetime, time, timedelta
from typing import Dict, List

import numpy as np

from database import get_connection


def _parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


CATEGORIES = ["SHIRT", "T_SHIRT", "TROUSER", "SHORT"]


def get_settings() -> dict:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    if not row:
        raise ValueError("Settings have not been configured yet. Call PUT /api/settings first.")
    settings = dict(row)
    settings["breaks"] = json.loads(settings.pop("breaks_json"))
    settings["category_targets"] = json.loads(settings.pop("category_targets_json") or "{}")
    return settings


def scheduled_hours_per_day(settings: dict) -> float:
    start = _parse_hhmm(settings["work_start_time"])
    end = _parse_hhmm(settings["work_end_time"])
    total_minutes = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
    return max(0.0, total_minutes / 60.0)


def fixed_break_hours_per_day(settings: dict) -> float:
    total_minutes = sum(b["duration_minutes"] for b in settings.get("breaks", []))
    return total_minutes / 60.0


def downtime_hours_for_day(day: date) -> float:
    day_start = datetime.combine(day, time.min)
    day_end = day_start + timedelta(days=1)

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT start, end FROM downtime_events WHERE start < ? AND end > ?",
            (day_end.isoformat(), day_start.isoformat()),
        ).fetchall()

    total_seconds = 0.0
    for row in rows:
        event_start = datetime.fromisoformat(row["start"])
        event_end = datetime.fromisoformat(row["end"])
        overlap_start = max(event_start, day_start)
        overlap_end = min(event_end, day_end)
        total_seconds += max(0.0, (overlap_end - overlap_start).total_seconds())
    return total_seconds / 3600.0


def effective_hours_for_day(day: date, settings: dict) -> float:
    """Scheduled shift hours, minus fixed tea/lunch breaks, minus any logged
    breakdown / power-failure downtime that overlaps that calendar day."""
    scheduled = scheduled_hours_per_day(settings)
    breaks = fixed_break_hours_per_day(settings)
    downtime = downtime_hours_for_day(day)
    return max(0.0, scheduled - breaks - downtime)


def daily_counts() -> List[Dict]:
    """All-time daily counts, unscoped by any target's start_date - this
    backs the Analytics history chart, which should keep showing everything
    ever packed even after a target reset zeroes out the dashboard KPIs."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT substr(timestamp, 1, 10) AS date, COUNT(*) AS count
            FROM garments
            GROUP BY date
            ORDER BY date
            """
        ).fetchall()
    return [{"date": row["date"], "count": row["count"]} for row in rows]


def _daily_counts_since(start_date: date, style_name: str = None) -> List[Dict]:
    query = "SELECT substr(timestamp, 1, 10) AS date, COUNT(*) AS count FROM garments WHERE timestamp >= :since"
    params = {"since": datetime.combine(start_date, time.min).isoformat()}
    if style_name:
        query += " AND style_name = :style_name"
        params["style_name"] = style_name
    query += " GROUP BY date ORDER BY date"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [{"date": row["date"], "count": row["count"]} for row in rows]


def _daily_rates_since(start_date: date, settings: dict, style_name: str = None) -> List[Dict]:
    """Pieces-per-effective-hour for every day since start_date that has at
    least one scan - scoped to the current target's window (and optionally
    one garment category), not all-time history. This is what makes
    'current pace' and therefore efficiency read as 0 right after a new
    target is set, instead of carrying over the previous target's rate."""
    rates = []
    for row in _daily_counts_since(start_date, style_name):
        day = datetime.strptime(row["date"], "%Y-%m-%d").date()
        hours = effective_hours_for_day(day, settings)
        rate = (row["count"] / hours) if hours > 0 else 0.0
        rates.append(
            {
                "date": row["date"],
                "count": row["count"],
                "effective_hours": round(hours, 2),
                "rate_per_hour": rate,
            }
        )
    return rates


def weighted_recent_rate(rates: List[Dict], window: int = 3) -> float:
    """Average pieces/effective-hour over the most recent days that actually
    had working hours, so a day fully wiped out by downtime doesn't skew it."""
    recent = [r for r in rates if r["effective_hours"] > 0][-window:]
    if not recent:
        return 0.0
    return sum(r["rate_per_hour"] for r in recent) / len(recent)


def _build_summary(target: int, total_packed: int, rates: List[Dict], settings: dict, start_date: date, due_date: date) -> dict:
    """The full remaining/ETA/efficiency/OT bundle for one target - the
    overall total and each of the four per-category targets all go through
    this exact same math, just with a different target figure, packed
    count, and rate history (already pre-scoped to the right category by
    the caller)."""
    current_rate_per_hour = weighted_recent_rate(rates, window=3)
    planned_daily_hours = max(0.0, scheduled_hours_per_day(settings) - fixed_break_hours_per_day(settings))

    remaining = max(0, target - total_packed)
    is_completed = target > 0 and total_packed >= target

    total_days_allocated = max(1, (due_date - start_date).days)
    total_hours_allocated = total_days_allocated * planned_daily_hours
    required_rate_per_hour = (target / total_hours_allocated) if total_hours_allocated > 0 else 0.0
    efficiency_pct = (
        (current_rate_per_hour / required_rate_per_hour) * 100 if required_rate_per_hour > 0 else None
    )

    estimated_days: int | None
    if current_rate_per_hour > 0 and planned_daily_hours > 0:
        daily_capacity = current_rate_per_hour * planned_daily_hours
        estimated_days = math.ceil(remaining / daily_capacity) if remaining > 0 else 0
    else:
        estimated_days = None  # not enough data yet to estimate a rate

    today = date.today()
    projected_completion = today + timedelta(days=estimated_days) if estimated_days is not None else None

    on_track = None
    delayed_days = None
    extra_hours_per_day = None

    if projected_completion is not None:
        on_track = projected_completion <= due_date
        if not on_track:
            delayed_days = (projected_completion - due_date).days
            remaining_days_until_due = max(1, (due_date - today).days)
            hours_available_until_due = remaining_days_until_due * planned_daily_hours
            hours_needed = remaining / current_rate_per_hour if current_rate_per_hour > 0 else float("inf")
            extra_hours_total = max(0.0, hours_needed - hours_available_until_due)
            extra_hours_per_day = extra_hours_total / remaining_days_until_due

    return {
        "target_pieces": target,
        "total_packed": total_packed,
        "remaining": remaining,
        "is_completed": is_completed,
        "current_rate_per_hour": round(current_rate_per_hour, 2),
        "required_rate_per_hour": round(required_rate_per_hour, 2),
        "efficiency_pct": round(efficiency_pct, 1) if efficiency_pct is not None else None,
        "planned_daily_hours": round(planned_daily_hours, 2),
        "estimated_days_to_target": estimated_days,
        "projected_completion_date": projected_completion.isoformat() if projected_completion else None,
        "due_date": due_date.isoformat(),
        "on_track": on_track,
        "delayed_days": delayed_days,
        "extra_hours_per_day": round(extra_hours_per_day, 2) if extra_hours_per_day is not None else None,
    }


def summary() -> dict:
    settings = get_settings()
    start_date = date.fromisoformat(settings["start_date"])
    due_date = date.fromisoformat(settings["due_date"])

    with get_connection() as conn:
        total_packed = conn.execute(
            "SELECT COUNT(*) AS n FROM garments WHERE timestamp >= ?",
            (datetime.combine(start_date, time.min).isoformat(),),
        ).fetchone()["n"]

    rates = _daily_rates_since(start_date, settings)
    overall = _build_summary(settings["target_pieces"], total_packed, rates, settings, start_date, due_date)

    category_targets = settings.get("category_targets", {})
    categories = {}
    for category in CATEGORIES:
        with get_connection() as conn:
            cat_packed = conn.execute(
                "SELECT COUNT(*) AS n FROM garments WHERE timestamp >= ? AND style_name = ?",
                (datetime.combine(start_date, time.min).isoformat(), category),
            ).fetchone()["n"]
        cat_rates = _daily_rates_since(start_date, settings, style_name=category)
        categories[category] = _build_summary(
            category_targets.get(category, 0), cat_packed, cat_rates, settings, start_date, due_date
        )

    overall["categories"] = categories
    return overall


def _predict_from_rates(rates: List[Dict], settings: dict) -> dict:
    """Same weighted-moving-average-blended-with-trend forecast, over
    whatever rate history the caller hands it - the overall forecast and
    each of the four per-category forecasts all share this, just fed a
    different (already category-filtered) rate history."""
    usable = [r for r in rates if r["effective_hours"] > 0]

    if not usable:
        return {
            "predicted_count": 0,
            "predicted_rate_per_hour": 0.0,
            "method": "no_data",
            "days_used": 0,
        }

    window = usable[-5:]
    weights = [5, 4, 3, 2, 1][-len(window):]
    predicted_rate = sum(w * r["rate_per_hour"] for w, r in zip(weights, window)) / sum(weights)

    method = "weighted_moving_average"
    if len(window) >= 3:
        x = np.arange(len(window))
        y = np.array([r["rate_per_hour"] for r in window])
        slope, intercept = np.polyfit(x, y, 1)
        trend_rate = max(0.0, float(slope * len(window) + intercept))
        predicted_rate = (predicted_rate + trend_rate) / 2
        method = "weighted_average_blended_with_linear_trend"

    tomorrow = date.today() + timedelta(days=1)
    tomorrow_hours = effective_hours_for_day(tomorrow, settings)
    predicted_count = round(predicted_rate * tomorrow_hours)

    return {
        "predicted_count": max(0, predicted_count),
        "predicted_rate_per_hour": round(predicted_rate, 2),
        "planned_effective_hours_tomorrow": round(tomorrow_hours, 2),
        "method": method,
        "days_used": len(window),
    }


def predict_next_day() -> dict:
    settings = get_settings()
    start_date = date.fromisoformat(settings["start_date"])

    overall = _predict_from_rates(_daily_rates_since(start_date, settings), settings)

    categories = {}
    for category in CATEGORIES:
        cat_rates = _daily_rates_since(start_date, settings, style_name=category)
        categories[category] = _predict_from_rates(cat_rates, settings)

    overall["categories"] = categories
    return overall
