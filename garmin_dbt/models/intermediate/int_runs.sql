select
    *
from {{ ref('stg_garmin__activities') }}
where activity_type = 'running'