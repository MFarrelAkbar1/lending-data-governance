-- Cleansed credit bureau records. One row per bureau credit, no rows dropped.

with source as (
    select * from {{ source('raw', 'bureau') }}
)

select
    "SK_ID_BUREAU"::bigint                                      as bureau_id,
    "SK_ID_CURR"::bigint                                        as applicant_id,
    {{ clean_category('"CREDIT_ACTIVE"') }}                     as credit_status,
    {{ clean_category('"CREDIT_CURRENCY"') }}                   as credit_currency,
    {{ clean_category('"CREDIT_TYPE"') }}                       as credit_type,
    "DAYS_CREDIT"::integer                                      as days_credit,
    "CREDIT_DAY_OVERDUE"::integer                               as credit_days_overdue,
    -- Values more than 100 years in the past are implausible: NULL plus flag.
    case when "DAYS_CREDIT_ENDDATE" < -36500 then null
         else "DAYS_CREDIT_ENDDATE"::integer end                as days_credit_enddate,
    coalesce("DAYS_CREDIT_ENDDATE" < -36500, false)             as is_days_credit_enddate_implausible,
    "DAYS_ENDDATE_FACT"::integer                                as days_enddate_fact,
    -- Closed before opened: kept as reported and flagged.
    coalesce("DAYS_ENDDATE_FACT" < "DAYS_CREDIT", false)        as is_closed_before_opened,
    case when "DAYS_CREDIT_UPDATE" < -36500 then null
         else "DAYS_CREDIT_UPDATE"::integer end                 as days_credit_update,
    coalesce("DAYS_CREDIT_UPDATE" < -36500, false)              as is_days_credit_update_implausible,
    "CNT_CREDIT_PROLONG"::integer                               as credit_prolong_count,
    {{ to_amount('"AMT_CREDIT_MAX_OVERDUE"') }}                 as credit_max_overdue_amount,
    {{ to_amount('"AMT_CREDIT_SUM"') }}                         as credit_sum_amount,
    -- Negative debt and limit are kept as reported and flagged (possible credit balance).
    {{ to_amount('"AMT_CREDIT_SUM_DEBT"') }}                    as credit_debt_amount,
    coalesce("AMT_CREDIT_SUM_DEBT" < 0, false)                  as is_negative_debt,
    {{ to_amount('"AMT_CREDIT_SUM_LIMIT"') }}                   as credit_limit_amount,
    coalesce("AMT_CREDIT_SUM_LIMIT" < 0, false)                 as is_negative_limit,
    {{ to_amount('"AMT_CREDIT_SUM_OVERDUE"') }}                 as credit_overdue_amount,
    {{ to_amount('"AMT_ANNUITY"') }}                            as annuity_amount,
    "_loaded_at"                                                as loaded_at,
    "_batch_id"                                                 as batch_id
from source
