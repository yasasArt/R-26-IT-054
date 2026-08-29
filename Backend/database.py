import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "threadscan.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS garments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    style_name TEXT NOT NULL,
    main_color TEXT NOT NULL,
    other_colors TEXT,
    confidence REAL NOT NULL,
    image_base64 TEXT,
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_garments_timestamp ON garments(timestamp);

CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    target_pieces INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    work_start_time TEXT NOT NULL,
    work_end_time TEXT NOT NULL,
    breaks_json TEXT NOT NULL DEFAULT '[]',
    category_targets_json TEXT NOT NULL DEFAULT '{}',
    count_since TEXT
);

CREATE TABLE IF NOT EXISTS downtime_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK (type IN ('breakdown', 'power_failure')),
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_downtime_start_end ON downtime_events(start, end);

CREATE TABLE IF NOT EXISTS device_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    camera_index INTEGER NOT NULL,
    camera_label TEXT NOT NULL
);
"""


def _migrate(conn: sqlite3.Connection):
    """CREATE TABLE IF NOT EXISTS only helps brand-new databases - this repo's
    threadscan.db already existed before category_targets_json/count_since
    were added, so a plain schema re-run wouldn't retroactively add them to
    that table."""
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(settings)")}
    if "category_targets_json" not in existing_columns:
        conn.execute("ALTER TABLE settings ADD COLUMN category_targets_json TEXT NOT NULL DEFAULT '{}'")
    if "count_since" not in existing_columns:
        # NULL here (rather than backfilling it from the existing
        # start_date) is deliberate - analytics.get_settings() falls back to
        # start_date-at-midnight whenever count_since is unset, which is
        # exactly the old behaviour this column replaces.
        conn.execute("ALTER TABLE settings ADD COLUMN count_since TEXT")

    # The adjustable detection-zone feature (and its roi_settings table) was
    # removed - drop the table on any database that already created it.
    conn.execute("DROP TABLE IF EXISTS roi_settings")


def init_db():
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


init_db()
