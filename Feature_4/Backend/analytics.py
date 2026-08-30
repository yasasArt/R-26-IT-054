import json
import math
from datetime import date, datetime, time, timedelta
from typing import Dict, List

import numpy as np

from Feature_4.Backend.database import get_connection


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

    # count_since is the precise moment "Total Packed" and the current-rate
    # calculations start counting from - distinct from start_date, which
    # only marks the beginning of the schedule window (due_date - start_date
    # = days allocated). Saving a new target moves both to now; completing a
    # target and auto-resetting only moves count_since, since the schedule
    # window itself hasn't changed. Falls back to start_date-at-midnight for
    # rows written before this column existed, or if it's ever cleared.
    start_date = date.fromisoformat(settings["start_date"])
    settings["count_since"] = settings["count_since"] or datetime.combine(start_date, time.min).isoformat()

    return settings


def scheduled_hours_per_day(settings: dict) -> float:
    start = _parse_hhmm(settings["work_start_time"])
    end = _parse_hhmm(settings["work_end_time"])
    total_minutes = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
    return max(0.0, total_minutes / 60.0)


def fixed_break_hours_per_day(settings: dict) -> float:
    total_minutes = sum(b["duration_minutes"] for b in settings.get("breaks", []))
    return total_minutes / 60.0


def downtime_hours_for_day(day: date, until: datetime = None) -> float:
    """Downtime overlapping `day`, optionally capped at `until` instead of
    the full calendar day - used for today's *elapsed-so-far* window so a
    breakdown scheduled later this afternoon doesn't reduce hours that
    haven't happened yet."""
    day_start = datetime.combine(day, time.min)
    day_end = day_start + timedelta(days=1)
    if until is not None:
        day_end = min(day_end, until)

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


def effective_hours_for_day(day: date, settings: dict, now: datetime = None) -> float:
    """Scheduled shift hours, minus fixed tea/lunch breaks, minus any logged
    breakdown/power-failure downtime that overlaps that calendar day.

    For TODAY specifically, this is capped to elapsed time since shift start
    (and only counts breaks/downtime that have actually started by now) -
    using the *full* planned day as the denominator for a day that isn't
    over yet was the reason Efficiency looked like it was constantly
    drifting: early in a shift the real pace divided by a full day's hours
    reads far too low, then climbs back up as the count "catches up" to
    what a finished day would have implied, all without the actual pace
    having changed. Past days are unaffected - they use the full scheduled
    day, exactly as before."""
    now = now or datetime.now()
    scheduled = scheduled_hours_per_day(settings)
    breaks = fixed_break_hours_per_day(settings)
    downtime_until = None

    if day == now.date():
        shift_start = datetime.combine(day, _parse_hhmm(settings["work_start_time"]))
        elapsed_hours = max(0.0, (now - shift_start).total_seconds() / 3600.0)
        scheduled = min(scheduled, elapsed_hours)

        elapsed_break_minutes = 0.0
        for b in settings.get("breaks", []):
            break_start = datetime.combine(day, _parse_hhmm(b["start_time"]))
            if now > break_start:
                elapsed_break_minutes += min(b["duration_minutes"], (now - break_start).total_seconds() / 60.0)
        breaks = elapsed_break_minutes / 60.0
        downtime_until = now

    downtime = downtime_hours_for_day(day, until=downtime_until)
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


def _daily_counts_since(count_since: str, style_name: str = None) -> List[Dict]:
    query = "SELECT substr(timestamp, 1, 10) AS date, COUNT(*) AS count FROM garments WHERE timestamp >= :since"
    params = {"since": count_since}
    if style_name:
        query += " AND style_name = :style_name"
        params["style_name"] = style_name
    query += " GROUP BY date ORDER BY date"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [{"date": row["date"], "count": row["count"]} for row in rows]


def _daily_rates_since(count_since: str, settings: dict, style_name: str = None) -> List[Dict]:
    """Pieces-per-effective-hour for every day since count_since that has at
    least one scan - scoped to the current counting cycle (and optionally
    one garment category), not all-time history. This is what makes
    'current pace' and therefore efficiency read as 0 right after a new
    target is set or a completed target auto-resets, instead of carrying
    over the previous cycle's rate."""
    rates = []
    for row in _daily_counts_since(count_since, style_name):
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


# Below this, a day's effective_hours is too small for its rate to mean
# anything - e.g. 1 piece packed 3 minutes into a shift reads as a 20
# pcs/hr pace. weighted_recent_rate excludes days under this so a fresh
# shift's first few minutes don't feed a wildly optimistic number into
# Projected Delivery before there's actually enough elapsed time to average
# out.
MIN_RELIABLE_HOURS = 0.5


def weighted_recent_rate(rates: List[Dict], window: int = 3) -> float:
    """Average pieces/effective-hour over the most recent days that actually
    had a reliable amount of working hours, so neither a day fully wiped
    out by downtime nor a day that's barely started yet can skew it."""
    recent = [r for r in rates if r["effective_hours"] >= MIN_RELIABLE_HOURS][-window:]
    if not recent:
        return 0.0
    return sum(r["rate_per_hour"] for r in recent) / len(recent)


def _find_completion_timestamp(count_since: str, target: int, style_name: str = None) -> str:
    """The exact timestamp of the garment that pushed the count up to
    target - the Nth matching row since count_since, computed straight from
    existing data rather than stored separately, so there's no extra
    mutable 'when did we complete' state to keep in sync or reset. This is
    what freezing the counter and reporting how long the order actually
    took are both built on."""
    if target <= 0:
        return None
    query = "SELECT timestamp FROM garments WHERE timestamp >= :since"
    params: dict = {"since": count_since}
    if style_name:
        query += " AND style_name = :style_name"
        params["style_name"] = style_name
    query += " ORDER BY timestamp ASC LIMIT 1 OFFSET :offset"
    params["offset"] = target - 1

    with get_connection() as conn:
        row = conn.execute(query, params).fetchone()
    return row["timestamp"] if row else None


def _build_summary(
    target: int,
    raw_packed: int,
    rates: List[Dict],
    settings: dict,
    start_date: date,
    due_date: date,
    count_since: str,
    style_name: str = None,
) -> dict:
    """The full remaining/ETA/efficiency/OT bundle for one target - the
    overall total and each of the four per-category targets all go through
    this exact same math, just with a different target figure, packed
    count, and rate history (already pre-scoped to the right category by
    the caller). raw_packed is the true, uncapped count - total_packed
    freezes at target once reached (garments detected afterward are still
    saved to the database for History Log/Analytics, they just stop being
    credited toward this target)."""
    current_rate_per_hour = weighted_recent_rate(rates, window=3)
    planned_daily_hours = max(0.0, scheduled_hours_per_day(settings) - fixed_break_hours_per_day(settings))

    is_completed = target > 0 and raw_packed >= target
    total_packed = min(raw_packed, target) if target > 0 else raw_packed
    remaining = max(0, target - total_packed)

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

    # Once completed, look up the exact moment it happened (the target-th
    # garment's own timestamp) so the operator can see precisely how long
    # the order actually took, and so any garments detected after that
    # instant are visibly "extra" rather than silently inflating the count.
    completed_at = None
    elapsed_hours = None
    elapsed_days = None
    overrun = 0
    if is_completed:
        completed_at = _find_completion_timestamp(count_since, target, style_name)
        if completed_at:
            since_dt = datetime.fromisoformat(count_since)
            completed_dt = datetime.fromisoformat(completed_at)
            elapsed_hours = max(0.0, (completed_dt - since_dt).total_seconds() / 3600.0)
            elapsed_days = max(1, (completed_dt.date() - since_dt.date()).days + 1)
        overrun = max(0, raw_packed - target)

    return {
        "target_pieces": target,
        "total_packed": total_packed,
        "raw_packed": raw_packed,
        "overrun": overrun,
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
        "total_days_allocated": total_days_allocated,
        "total_hours_allocated": round(total_hours_allocated, 2),
        "completed_at": completed_at,
        "elapsed_hours": round(elapsed_hours, 2) if elapsed_hours is not None else None,
        "elapsed_days": elapsed_days,
    }


def summary() -> dict:
    settings = get_settings()
    start_date = date.fromisoformat(settings["start_date"])
    due_date = date.fromisoformat(settings["due_date"])
    count_since = settings["count_since"]

    with get_connection() as conn:
        raw_packed = conn.execute(
            "SELECT COUNT(*) AS n FROM garments WHERE timestamp >= ?",
            (count_since,),
        ).fetchone()["n"]

    rates = _daily_rates_since(count_since, settings)
    overall = _build_summary(settings["target_pieces"], raw_packed, rates, settings, start_date, due_date, count_since)

    category_targets = settings.get("category_targets", {})
    categories = {}
    for category in CATEGORIES:
        with get_connection() as conn:
            cat_raw_packed = conn.execute(
                "SELECT COUNT(*) AS n FROM garments WHERE timestamp >= ? AND style_name = ?",
                (count_since, category),
            ).fetchone()["n"]
        cat_rates = _daily_rates_since(count_since, settings, style_name=category)
        categories[category] = _build_summary(
            category_targets.get(category, 0), cat_raw_packed, cat_rates, settings, start_date, due_date,
            count_since, style_name=category,
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
    count_since = settings["count_since"]

    overall = _predict_from_rates(_daily_rates_since(count_since, settings), settings)

    categories = {}
    for category in CATEGORIES:
        cat_rates = _daily_rates_since(count_since, settings, style_name=category)
        categories[category] = _predict_from_rates(cat_rates, settings)

    overall["categories"] = categories
    return overall


def reset_progress() -> dict:
    """Bumps count_since to right now, without touching target_pieces,
    category_targets, start_date, due_date, or breaks. Used when a target
    is completed and the dashboard auto-resets for the next cycle - unlike
    saving settings (which also treats the moment as the start of a new
    schedule window), this only starts a fresh counting cycle inside the
    *same* target/schedule the operator already configured. Every garment
    record stays in the database untouched; only the pointer that decides
    which of them count toward 'Total Packed' moves forward."""
    now = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute("UPDATE settings SET count_since = ? WHERE id = 1", (now,))
    return {"count_since": now}
