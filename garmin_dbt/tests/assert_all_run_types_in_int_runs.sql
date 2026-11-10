-- Fails if a running-like activity was filtered out of int_runs
select activity_id, activity_type
from {{ ref('stg_garmin__activities') }} s
where activity_type ilike '%run%'
and not exists (
    select 1
    from {{ ref('int_runs') }} r
    where r.activity_id = s.activity_id
)