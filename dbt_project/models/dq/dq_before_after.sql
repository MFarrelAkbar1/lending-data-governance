-- Same rule, before and after cleansing: raw-level vs staging-level result
-- for every rule_id that is tested in both layers, latest run only.

with latest as (
    select * from {{ ref('dq_results') }}
    where is_latest_run and rule_id is not null
),

raw_layer as (
    select * from latest where layer = 'raw'
),

staging_layer as (
    select * from latest where layer = 'staging'
)

select
    r.rule_id,
    r.source_table,
    r.dq_dimension,
    r.test_name                                  as raw_test_name,
    s.test_name                                  as staging_test_name,
    r.status                                     as raw_status,
    s.status                                     as staging_status,
    r.failures                                   as raw_failures,
    s.failures                                   as staging_failures,
    r.failures - s.failures                      as failures_resolved,
    case
        when r.status = 'pass' and s.status = 'pass' then 'clean in both'
        when r.status <> 'pass' and s.status = 'pass' then 'resolved by cleansing'
        when r.status <> 'pass' and s.status <> 'pass' then 'still open (accepted)'
        else 'regressed'
    end                                          as outcome
from raw_layer r
join staging_layer s on r.rule_id = s.rule_id
