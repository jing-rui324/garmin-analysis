select
    activity_id,
    start_time,
    ingested_at,
    source_endpoint,

    payload ->> 'activityName' as activity_name,

    -- IDs / Types
    payload -> 'activityType' ->> 'typeKey' as activity_type,
    (payload -> 'activityType' ->> 'typeId')::int as type_id,
    (payload -> 'activityType' ->> 'parentTypeId')::int as parent_type_id,

    -- Times
    (payload ->> 'startTimeLocal')::timestamp as start_time_local,
    round((payload ->> 'movingDuration')::numeric, 2) as moving_duration_seconds,
    round((payload ->> 'elapsedDuration')::numeric, 2) as elapsed_duration_seconds,

    -- Measures
    round((payload ->> 'distance')::numeric, 2) as distance_meters,
    round((payload ->> 'duration')::numeric, 2) as duration_seconds,
    (payload ->> 'averageHR')::numeric as average_hr,
    (payload ->> 'maxHR')::numeric as max_hr,
    (payload ->> 'averageSpeed')::numeric as average_speed_mps,
    round((payload ->> 'elevationGain')::numeric, 2) as elevation_gain_meters,

    payload
from {{ source('garmin_raw', 'garmin_activities') }}