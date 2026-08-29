import json
from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import analytics
from database import get_connection
from models import CameraDevice, DowntimeEvent, GarmentData, Settings

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "ThreadScan Backend with SQLite is Running Successfully!"}


# ============================================================ Garments =====

@app.get("/api/garments/")
def get_all_garments():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM garments ORDER BY id DESC").fetchall()

    garments = []
    for row in rows:
        garment = dict(row)
        garment["_id"] = str(garment.pop("id"))
        garments.append(garment)
    return garments


@app.post("/api/garments/")
def save_garment(garment: GarmentData):
    garment_dict = garment.model_dump()
    garment_dict["timestamp"] = datetime.now().isoformat()

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO garments (style_name, main_color, other_colors, confidence, image_base64, timestamp)
            VALUES (:style_name, :main_color, :other_colors, :confidence, :image_base64, :timestamp)
            """,
            garment_dict,
        )
        inserted_id = cursor.lastrowid

    return {"status": "success", "message": "Garment saved to SQLite", "id": str(inserted_id)}


@app.get("/api/garments/latest")
def get_latest_garment():
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM garments ORDER BY id DESC LIMIT 1").fetchone()

    if row:
        garment = dict(row)
        garment["_id"] = str(garment.pop("id"))
        return garment
    return None


@app.delete("/api/garments/")
def delete_all_garments():
    """Permanently deletes every garment record - used by the History
    Management card on the Target & Schedule page. Irreversible; the
    frontend is responsible for confirming with the operator first."""
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM garments")
        deleted_count = cursor.rowcount

    return {"status": "success", "deleted_count": deleted_count}


# ============================================================ Settings =====

@app.get("/api/settings")
def get_settings_route():
    try:
        return analytics.get_settings()
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@app.put("/api/settings")
def update_settings(settings: Settings):
    settings_dict = settings.model_dump(mode="json")
    breaks_json = json.dumps(settings_dict.pop("breaks"))
    category_targets_json = json.dumps(settings_dict.pop("category_targets"))

    # start_date is now a normal operator-editable field (schedule window
    # start, used for total_days_allocated = due_date - start_date) - it's
    # trusted as-is from the client rather than forced to today. Saving is
    # still how a new counting cycle begins though: count_since always moves
    # to now, which is what makes "Total Packed"/"Efficiency" read as 0
    # immediately after (both are computed from garments/daily rates with
    # timestamp >= count_since), independent of whatever start_date was set to.
    count_since = datetime.now().isoformat()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO settings (id, target_pieces, start_date, due_date, work_start_time, work_end_time, breaks_json, category_targets_json, count_since)
            VALUES (1, :target_pieces, :start_date, :due_date, :work_start_time, :work_end_time, :breaks_json, :category_targets_json, :count_since)
            ON CONFLICT(id) DO UPDATE SET
                target_pieces = excluded.target_pieces,
                start_date = excluded.start_date,
                due_date = excluded.due_date,
                work_start_time = excluded.work_start_time,
                work_end_time = excluded.work_end_time,
                breaks_json = excluded.breaks_json,
                category_targets_json = excluded.category_targets_json,
                count_since = excluded.count_since
            """,
            {
                **settings_dict,
                "breaks_json": breaks_json,
                "category_targets_json": category_targets_json,
                "count_since": count_since,
            },
        )

    return {"status": "success", "message": "Settings updated", "start_date": settings_dict["start_date"]}


@app.post("/api/settings/reset-progress")
def reset_progress_route():
    """Bumps the counting baseline to now without touching target_pieces,
    category_targets, start_date, due_date, or breaks - called automatically
    by the frontend when a target is completed, to start a fresh counting
    cycle within the same configured target/schedule. No garment record is
    ever touched by this."""
    try:
        return analytics.reset_progress()
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


# ============================================================== Device =====

@app.get("/api/device/camera")
def get_camera_device():
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM device_settings WHERE id = 1").fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No camera has been configured yet.")
    device = dict(row)
    device.pop("id", None)
    return device


@app.put("/api/device/camera")
def update_camera_device(device: CameraDevice):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO device_settings (id, camera_index, camera_label)
            VALUES (1, :camera_index, :camera_label)
            ON CONFLICT(id) DO UPDATE SET
                camera_index = excluded.camera_index,
                camera_label = excluded.camera_label
            """,
            device.model_dump(),
        )
    return {"status": "success", "message": "Camera device saved"}


# ============================================================ Downtime =====

@app.post("/api/downtime")
def log_downtime(event: DowntimeEvent):
    if event.end <= event.start:
        raise HTTPException(status_code=400, detail="end must be after start")

    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO downtime_events (type, start, end, reason) VALUES (?, ?, ?, ?)",
            (event.type, event.start.isoformat(), event.end.isoformat(), event.reason),
        )
        inserted_id = cursor.lastrowid

    return {"status": "success", "id": str(inserted_id)}


@app.get("/api/downtime")
def list_downtime(day: Optional[str] = Query(default=None, description="YYYY-MM-DD, omit for all events")):
    query = "SELECT * FROM downtime_events"
    params: tuple = ()

    if day:
        target_day = date.fromisoformat(day)
        day_start = datetime.combine(target_day, datetime.min.time())
        day_end = datetime.combine(target_day, datetime.max.time())
        query += " WHERE start <= ? AND end >= ?"
        params = (day_end.isoformat(), day_start.isoformat())

    query += " ORDER BY start DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    events = []
    for row in rows:
        event = dict(row)
        event["_id"] = str(event.pop("id"))
        events.append(event)
    return events


# =============================================================== Stats =====

@app.get("/api/stats/daily")
def stats_daily():
    return analytics.daily_counts()


@app.get("/api/stats/summary")
def stats_summary():
    try:
        return analytics.summary()
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@app.get("/api/predict/next-day")
def predict_next_day():
    try:
        return analytics.predict_next_day()
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
