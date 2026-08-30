-- Migration 003: Make controller deliveries safely replayable.

ALTER TABLE iot_events ADD COLUMN event_key TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_iot_events_session_event_key
ON iot_events (session_id, event_key)
WHERE event_key IS NOT NULL;

