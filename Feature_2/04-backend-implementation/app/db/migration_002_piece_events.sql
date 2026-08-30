-- Migration 002: Make every confirmed piece idempotent and auditable.

ALTER TABLE piece_events ADD COLUMN event_key TEXT;
ALTER TABLE piece_events ADD COLUMN sewing_started_at TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_piece_events_session_event_key
ON piece_events (session_id, event_key)
WHERE event_key IS NOT NULL;
