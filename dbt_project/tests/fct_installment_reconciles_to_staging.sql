{{ config(
    severity='error',
    meta={'dq_dimension': 'consistency', 'rule_id': 'INST_MART_RECONCILES',
          'dq_table': 'fct_installment', 'layer': 'marts'}
) }}

-- Aggregating split payments to installment grain must not lose or invent money:
-- total paid and payment count in the mart equal the payment-level staging totals.

with staging as (
    select coalesce(sum(payment_amount), 0) as paid, count(payment_amount) as payments
    from {{ ref('stg_installments') }}
),

mart as (
    select sum(paid_amount) as paid, sum(payment_count) as payments
    from {{ ref('fct_installment') }}
)

select staging.paid as staging_paid, mart.paid as mart_paid,
       staging.payments as staging_payments, mart.payments as mart_payments
from staging cross join mart
where abs(staging.paid - mart.paid) > 0.01
   or staging.payments <> mart.payments
