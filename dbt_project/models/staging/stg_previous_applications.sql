-- Cleansed previous Home Credit applications. One row per previous application, no rows dropped.

{% set placeholder_days = ['DAYS_FIRST_DRAWING', 'DAYS_FIRST_DUE', 'DAYS_LAST_DUE_1ST_VERSION', 'DAYS_LAST_DUE', 'DAYS_TERMINATION'] %}

with source as (
    select * from {{ source('raw', 'previous_application') }}
)

select
    "SK_ID_PREV"::bigint                                        as previous_application_id,
    "SK_ID_CURR"::bigint                                        as applicant_id,
    {{ clean_category('"NAME_CONTRACT_TYPE"') }}                as contract_type,
    {{ clean_category('"NAME_CONTRACT_STATUS"') }}              as contract_status,
    {{ clean_category('"CODE_REJECT_REASON"') }}                as reject_reason,
    {{ clean_category('"NAME_CASH_LOAN_PURPOSE"') }}            as cash_loan_purpose,
    {{ clean_category('"NAME_PAYMENT_TYPE"') }}                 as payment_type,
    {{ clean_category('"NAME_CLIENT_TYPE"') }}                  as client_type,
    {{ clean_category('"NAME_GOODS_CATEGORY"') }}               as goods_category,
    {{ clean_category('"NAME_PORTFOLIO"') }}                    as portfolio,
    {{ clean_category('"NAME_PRODUCT_TYPE"') }}                 as product_type,
    {{ clean_category('"CHANNEL_TYPE"') }}                      as channel_type,
    {{ clean_category('"NAME_SELLER_INDUSTRY"') }}              as seller_industry,
    {{ clean_category('"NAME_YIELD_GROUP"') }}                  as yield_group,
    -- -1 is a sentinel for "no seller place" (issue DQ-008).
    nullif("SELLERPLACE_AREA", -1)::integer                     as seller_place_area,
    {{ to_amount('"AMT_APPLICATION"') }}                        as application_amount,
    {{ to_amount('"AMT_CREDIT"') }}                             as credit_amount,
    {{ to_amount('"AMT_ANNUITY"') }}                            as annuity_amount,
    {{ to_amount('"AMT_DOWN_PAYMENT"') }}                       as down_payment_amount,
    {{ to_amount('"AMT_GOODS_PRICE"') }}                        as goods_price_amount,
    "CNT_PAYMENT"::integer                                      as payment_count,
    "DAYS_DECISION"::integer                                    as days_decision,
    {%- for col in placeholder_days %}
    {{ clean_days('"' ~ col ~ '"') }} as {{ col | lower }},
    {{ days_placeholder_flag('"' ~ col ~ '"') }} as is_{{ col | lower }}_placeholder,
    {%- endfor %}
    {{ yn_to_bool('"FLAG_LAST_APPL_PER_CONTRACT"') }}           as is_last_application_per_contract,
    "_loaded_at"                                                as loaded_at,
    "_batch_id"                                                 as batch_id
from source
