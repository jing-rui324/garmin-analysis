CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.garmin_activities(
    activity_id BIGINT PRIMARY KEY,
    start_time TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_endpoint TEXT NOT NULL
);