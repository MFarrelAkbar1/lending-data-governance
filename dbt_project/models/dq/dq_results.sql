-- Every stored test result with run sequence and pass flags.

with history as (
    select * from {{ source('dq', 'dq_results_history') }}
),

runs as (
    select run_id, run_at, row_number() over (order by run_at) as run_number
    from (select distinct run_id, run_at from history) r
)

select
    h.run_id,
    r.run_number,
    r.run_number = max(r.run_number) over ()                  as is_latest_run,
    h.run_at,
    h.data_batch_id,
    h.test_name,
    h.test_type,
    h.rule_id,
    h.layer,
    h.source_table,
    h.model_name,
    h.column_name,
    h.dq_dimension,
    h.severity,
    h.status,
    h.status = 'pass'                                          as is_pass,
    coalesce(h.failures, 0)                                    as failures,
    h.rows_checked,
    -- Share of checked rows not returned by the test. Tests that return keys or
    -- value groups instead of rows (unique, accepted_values) make this an estimate.
    case when h.rows_checked > 0
         then round(100 * (1 - least(coalesce(h.failures, 0), h.rows_checked)::numeric / h.rows_checked), 3)
    end                                                        as row_conformance_pct,
    h.description
from history h
join runs r on h.run_id = r.run_id
