-- Installment payments at payment level. No rows dropped.
-- Raw rows are not unique on (SK_ID_PREV, NUM_INSTALMENT_NUMBER, NUM_INSTALMENT_VERSION)
-- because one installment can be paid in several parts (issue DQ-007). payment_seq
-- numbers the payments within an installment so the staging grain is unique.

with source as (
    select * from {{ source('raw', 'installments_payments') }}
),

previous_ids as (
    select distinct "SK_ID_PREV" from {{ source('raw', 'previous_application') }}
)

select
    s."SK_ID_PREV"::bigint                                      as previous_application_id,
    s."SK_ID_CURR"::bigint                                      as applicant_id,
    s."NUM_INSTALMENT_VERSION"::integer                         as instalment_version,
    s."NUM_INSTALMENT_NUMBER"::integer                          as instalment_number,
    row_number() over (
        partition by s."SK_ID_PREV", s."NUM_INSTALMENT_NUMBER", s."NUM_INSTALMENT_VERSION"
        order by s."DAYS_ENTRY_PAYMENT" nulls last, s."AMT_PAYMENT"
    )                                                           as payment_seq,
    s."DAYS_INSTALMENT"::integer                                as days_instalment_due,
    s."DAYS_ENTRY_PAYMENT"::integer                             as days_entry_payment,
    {{ to_amount('s."AMT_INSTALMENT"') }}                       as instalment_amount,
    {{ to_amount('s."AMT_PAYMENT"') }}                          as payment_amount,
    s."AMT_PAYMENT" is null                                     as is_payment_missing,
    coalesce(s."AMT_INSTALMENT" > 0 and s."AMT_PAYMENT" > 2 * s."AMT_INSTALMENT", false)
                                                                as is_overpayment,
    p."SK_ID_PREV" is null                                      as is_orphan_previous_application,
    s."_loaded_at"                                              as loaded_at,
    s."_batch_id"                                               as batch_id
from source s
left join previous_ids p on s."SK_ID_PREV" = p."SK_ID_PREV"
