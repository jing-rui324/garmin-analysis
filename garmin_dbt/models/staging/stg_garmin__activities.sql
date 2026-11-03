select
    activity_id,
    start_time,
    ingested_at,
    source_endpoint,

    payload ->> 'activityName' as activity_name,
    payload -> 'activityType' ->> 'typeKey' as activity_type,

    (payload ->> 'distance')::numeric as distance_meters,
    (payload ->> 'duration')::numeric as duration_seconds,
    (payload ->> 'averageHR')::numeric as average_hr,
    (payload ->> 'maxHR')::numeric as max_hr,
    (payload ->> 'elevationGain')::numeric as elevation_gain_meters,

    payload
from {{ source('garmin_raw', 'garmin_activities') }}