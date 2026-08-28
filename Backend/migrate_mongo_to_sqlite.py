"""One-time migration: copies existing data from the MongoDB Atlas cluster
(used in the previous phase) into the new local SQLite database. Safe to
re-run - garments/downtime are only inserted if the target table is empty,
and settings are upserted."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

from database import get_connection

load_dotenv(Path(__file__).resolve().parent / ".env")

MONGO_URI = os.environ["MONGO_URI"]


def migrate():
    mongo = MongoClient(MONGO_URI)
    mongo_db = mongo["threadscan_db"]

    with get_connection() as conn:
        existing_garments = conn.execute("SELECT COUNT(*) AS n FROM garments").fetchone()["n"]
        if existing_garments:
            print(f"Skipping garments - {existing_garments} rows already present in SQLite.")
        else:
            garments = list(mongo_db["garments"].find().sort("_id", 1))
            for doc in garments:
                timestamp = doc.get("timestamp")
                if hasattr(timestamp, "isoformat"):
                    timestamp = timestamp.isoformat()
                conn.execute(
                    """
                    INSERT INTO garments (style_name, main_color, other_colors, confidence, image_base64, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc.get("style_name"),
                        doc.get("main_color"),
                        doc.get("other_colors"),
                        doc.get("confidence"),
                        doc.get("image_base64"),
                        timestamp,
                    ),
                )
            print(f"Migrated {len(garments)} garment scans.")

        existing_downtime = conn.execute("SELECT COUNT(*) AS n FROM downtime_events").fetchone()["n"]
        if existing_downtime:
            print(f"Skipping downtime events - {existing_downtime} rows already present in SQLite.")
        else:
            events = list(mongo_db["downtime_events"].find().sort("_id", 1))
            for doc in events:
                start = doc.get("start")
                end = doc.get("end")
                if hasattr(start, "isoformat"):
                    start = start.isoformat()
                if hasattr(end, "isoformat"):
                    end = end.isoformat()
                conn.execute(
                    "INSERT INTO downtime_events (type, start, end, reason) VALUES (?, ?, ?, ?)",
                    (doc.get("type"), start, end, doc.get("reason")),
                )
            print(f"Migrated {len(events)} downtime events.")

        settings_doc = mongo_db["settings"].find_one({"_id": "singleton"})
        if settings_doc:
            breaks_json = json.dumps(settings_doc.get("breaks", []))
            conn.execute(
                """
                INSERT INTO settings (id, target_pieces, start_date, due_date, work_start_time, work_end_time, breaks_json)
                VALUES (1, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    target_pieces = excluded.target_pieces,
                    start_date = excluded.start_date,
                    due_date = excluded.due_date,
                    work_start_time = excluded.work_start_time,
                    work_end_time = excluded.work_end_time,
                    breaks_json = excluded.breaks_json
                """,
                (
                    settings_doc.get("target_pieces"),
                    settings_doc.get("start_date"),
                    settings_doc.get("due_date"),
                    settings_doc.get("work_start_time"),
                    settings_doc.get("work_end_time"),
                    breaks_json,
                ),
            )
            print("Migrated settings.")
        else:
            print("No settings document found in MongoDB - skipping.")

    mongo.close()
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
