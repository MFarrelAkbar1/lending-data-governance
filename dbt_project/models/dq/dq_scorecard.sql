-- DQ scorecard: pass rate per run, layer, table and dimension, plus an
-- 'overall' row per table. dq_score_pct = tests passed / tests run * 100
-- (a warn counts as not passed). Trend columns compare with the previous run.

with results as (
    select * from {{ ref('dq_results') }}
),

by_dimension as (
    select run_id, run_number, is_latest_run, run_at, layer, source_table, model_name, dq_dimension,
           count(*)                                     as tests_run,
           count(*) filter (where status = 'pass')      as tests_passed,
           count(*) filter (where status = 'warn')      as tests_warned,
           count(*) filter (where status in ('fail', 'error')) as tests_failed,
           sum(failures)                                as failing_records,
           round(avg(row_conformance_pct), 3)           as avg_row_conformance_pct
    from results
    group by 1, 2, 3, 4, 5, 6, 7, 8
),

overall as (
    select run_id, run_number, is_latest_run, run_at, layer, source_table, model_name,
           'overall'                                    as dq_dimension,
           count(*)                                     as tests_run,
           count(*) filter (where status = 'pass')      as tests_passed,
           count(*) filter (where status = 'warn')      as tests_warned,
           count(*) filter (where status in ('fail', 'error')) as tests_failed,
           sum(failures)                                as failing_records,
           round(avg(row_conformance_pct), 3)           as avg_row_conformance_pct
    from results
    group by 1, 2, 3, 4, 5, 6, 7
),

combined as (
    select * from by_dimension
    union all
    select * from overall
)

select
    *,
    round(100.0 * tests_passed / tests_run, 1)                as dq_score_pct,
    lag(round(100.0 * tests_passed / tests_run, 1)) over (
        partition by layer, model_name, dq_dimension order by run_number
    )                                                         as previous_dq_score_pct,
    round(100.0 * tests_passed / tests_run, 1) - lag(round(100.0 * tests_passed / tests_run, 1)) over (
        partition by layer, model_name, dq_dimension order by run_number
    )                                                         as dq_score_change
from combined
