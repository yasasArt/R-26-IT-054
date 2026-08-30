CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_number TEXT NOT NULL COLLATE NOCASE UNIQUE,
    name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 2 AND 120),
    sewing_line TEXT NOT NULL CHECK (length(trim(sewing_line)) BETWEEN 1 AND 80),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_employees_active_name
ON employees (is_active, name COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS device_configuration (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    camera_index INTEGER,
    camera_label TEXT,
    camera_tested INTEGER NOT NULL DEFAULT 0 CHECK (camera_tested IN (0, 1)),
    controller_device_id TEXT,
    controller_name TEXT,
    controller_connected INTEGER NOT NULL DEFAULT 0
        CHECK (controller_connected IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

INSERT OR IGNORE INTO device_configuration (
    id,
    camera_tested,
    controller_connected,
    created_at,
    updated_at
) VALUES (
    1,
    0,
    0,
    strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
    strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
);

CREATE TABLE IF NOT EXISTS production_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    employee_number_snapshot TEXT NOT NULL,
    employee_name_snapshot TEXT NOT NULL,
    sewing_line_snapshot TEXT NOT NULL,
    target_pieces INTEGER NOT NULL CHECK (target_pieces > 0),
    session_mode TEXT NOT NULL
        CHECK (session_mode IN ('PRODUCTION', 'VALIDATION')),
    status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'COMPLETED', 'CANCELLED')),
    operator_mode TEXT NOT NULL DEFAULT 'NORMAL'
        CHECK (operator_mode IN ('NORMAL', 'REWORK', 'DOWNTIME')),
    camera_index_snapshot INTEGER,
    camera_label_snapshot TEXT,
    controller_device_id_snapshot TEXT,
    controller_name_snapshot TEXT,
    total_pieces INTEGER NOT NULL DEFAULT 0 CHECK (total_pieces >= 0),
    average_cycle_seconds REAL CHECK (
        average_cycle_seconds IS NULL OR average_cycle_seconds >= 0
    ),
    first_sewing_started_at TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (employee_id) REFERENCES employees(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_production_session
ON production_sessions (status)
WHERE status = 'ACTIVE';

CREATE INDEX IF NOT EXISTS idx_sessions_employee_started
ON production_sessions (employee_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_sessions_status_started
ON production_sessions (status, started_at DESC);

CREATE TABLE IF NOT EXISTS piece_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    employee_id INTEGER NOT NULL,
    piece_number INTEGER NOT NULL CHECK (piece_number > 0),
    cycle_seconds REAL NOT NULL CHECK (cycle_seconds > 0),
    confidence REAL CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    event_source TEXT NOT NULL DEFAULT 'VISION'
        CHECK (event_source IN ('VISION', 'VALIDATION', 'MANUAL_TEST')),
    completed_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES production_sessions(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    FOREIGN KEY (employee_id) REFERENCES employees(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    UNIQUE (session_id, piece_number)
);

CREATE INDEX IF NOT EXISTS idx_piece_events_session_completed
ON piece_events (session_id, completed_at);

CREATE INDEX IF NOT EXISTS idx_piece_events_employee_completed
ON piece_events (employee_id, completed_at);

CREATE TABLE IF NOT EXISTS iot_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    employee_id INTEGER NOT NULL,
    event_type TEXT NOT NULL
        CHECK (event_type IN ('REWORK', 'DOWNTIME', 'RESET', 'CONNECTED', 'DISCONNECTED')),
    mode_before TEXT NOT NULL
        CHECK (mode_before IN ('NORMAL', 'REWORK', 'DOWNTIME')),
    mode_after TEXT NOT NULL
        CHECK (mode_after IN ('NORMAL', 'REWORK', 'DOWNTIME')),
    device_name TEXT,
    device_id TEXT,
    event_source TEXT NOT NULL
        CHECK (event_source IN ('PHYSICAL_CONTROLLER', 'VALIDATION', 'SYSTEM')),
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES production_sessions(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    FOREIGN KEY (employee_id) REFERENCES employees(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_iot_events_session_occurred
ON iot_events (session_id, occurred_at);

CREATE INDEX IF NOT EXISTS idx_iot_events_employee_occurred
ON iot_events (employee_id, occurred_at);
