select
    activity_id,
    start_time_local::date as activity_date,
    start_time_local,
    activity_name,
    activity_type,
    is_treadmill,
    distance_km,
    duration_minutes,
    pace_min_per_km,
    average_hr,
    max_hr,
    elevation_gain_meters

from {{ ref('int_runs') }}