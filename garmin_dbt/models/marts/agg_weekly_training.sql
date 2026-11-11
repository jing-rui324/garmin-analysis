with runs as (
    select activity_id,
           activity_date,
           distance_km,
           duration_minutes
    from {{ ref('fct_runs') }}
),

weekly as (
    select date_trunc('week', activity_date)::date as week_start_date,
           count(activity_id) as total_runs,
           sum(distance_km) as total_distance_km,
           sum(duration_minutes) as total_duration_minutes,
           sum(duration_minutes) / nullif(sum(distance_km), 0) as pace_min_per_km,
           max(distance_km) as longest_run_km
    from runs
    group by 1
),

date_spine as(
    select generate_series(
        (select min(week_start_date) from weekly),
        (date_trunc('week', current_date)::date),
        interval '1 week'
    )::date as week_start_date
),

filled as(
    select
    ds.week_start_date,
    ds.week_start_date = (date_trunc('week', current_date)::date) as is_current_week,
    coalesce(w.total_runs, 0) as total_runs,
    coalesce(w.total_distance_km, 0) as total_distance_km,
    coalesce(w.total_duration_minutes, 0) as total_duration_minutes,
    w.pace_min_per_km,
    coalesce(w.longest_run_km, 0) as longest_run_km
from date_spine ds
left join weekly w
on ds.week_start_date = w.week_start_date
)

select
    *,
    case
        when is_current_week then null                   -- choice 3: current week excluded
        when count(*) over w4 < 4 then null              -- choice 2: fewer than 4 weeks of history
        else avg(total_distance_km) over w4
    end as rolling_4wk_distance_km
from filled
window w4 as (
    order by week_start_date
    rows between 3 preceding and current row
)
