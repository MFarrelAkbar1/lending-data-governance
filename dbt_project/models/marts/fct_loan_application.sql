-- One row per current loan application with contract and amount fields,
-- plus counts of related bureau credits and previous applications.

with bureau_counts as (
    select applicant_id, count(*) as bureau_credit_count
    from {{ ref('stg_bureau') }}
    group by applicant_id
),

previous_counts as (
    select applicant_id, count(*) as previous_application_count
    from {{ ref('stg_previous_applications') }}
    group by applicant_id
)

select
    a.applicant_id,
    a.contract_type,
    a.credit_amount,
    a.annuity_amount,
    a.goods_price_amount,
    a.income_total_amount,
    round(a.credit_amount / nullif(a.income_total_amount, 0), 4)  as credit_to_income_ratio,
    round(a.annuity_amount / nullif(a.income_total_amount, 0), 4) as annuity_to_income_ratio,
    a.target_default_flag,
    coalesce(b.bureau_credit_count, 0)                            as bureau_credit_count,
    coalesce(p.previous_application_count, 0)                     as previous_application_count,
    a.loaded_at
from {{ ref('stg_applications') }} a
left join bureau_counts b on a.applicant_id = b.applicant_id
left join previous_counts p on a.applicant_id = p.applicant_id
