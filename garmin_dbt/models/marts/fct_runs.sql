select
    activity_id,
    start_time,
    activity_type,
    distance_meters / 1000.0 as distance_km,
    duration_seconds / 60.0 as duration_minutes,
    (duration_seconds / 60.0)
        / nullif(distance_meters / 1000.0, 0) as pace_min_per_km,
    average_hr,
    max_hr,

    start_time at time zone 'Asia/Singapore' as start_time_sgt,
    cast(start_time at time zone 'Asia/Singapore' as date) as activity_date_sgt

from {{ ref('int_runs') }}