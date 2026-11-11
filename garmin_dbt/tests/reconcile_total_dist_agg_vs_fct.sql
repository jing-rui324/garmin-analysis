with agg_weekly_total as (
    select sum(total_distance_km) as total_km,
    sum(total_runs) as total_runs
    from {{ ref('agg_weekly_training') }}
),

runs_total as (
    select sum(distance_km) as total_km,
    count(activity_id) as total_runs
    from {{ ref('fct_runs') }}
)

select w.total_km as weekly_km, r.total_km as runs_km, 
       w.total_runs as weekly_runs, r.total_runs as runs_count
from agg_weekly_total w, runs_total r
where abs(w.total_km - r.total_km) > 0.01 or w.total_runs != r.total_runs