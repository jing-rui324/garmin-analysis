WITH runs AS (
    SELECT *
    FROM {{ ref('stg_garmin__activities') }}
    WHERE type_id = 1 OR parent_type_id = 1
),

converted AS (
    SELECT
        activity_id,
        start_time,
        start_time_local,
        activity_name,
        activity_type,
        activity_type = 'treadmill_running' AS is_treadmill,
        distance_meters,
        distance_meters / 1000.0 AS distance_km,
        duration_seconds,
        duration_seconds / 60.0 AS duration_minutes,
        moving_duration_seconds,
        elapsed_duration_seconds,
        average_hr,
        max_hr,
        average_speed_mps,
        elevation_gain_meters
    FROM runs
),

final AS (
    SELECT *,
    duration_minutes / NULLIF(distance_km, 0) AS pace_min_per_km
    FROM converted
)

SELECT * FROM final