-- Monthly bureau credit status. One row per bureau credit per month, no rows dropped.

with source as (
    select * from {{ source('raw', 'bureau_balance') }}
)

select
    "SK_ID_BUREAU"::bigint                                      as bureau_id,
    "MONTHS_BALANCE"::integer                                   as months_balance,
    trim("STATUS")                                              as status_code,
    case trim("STATUS")
        when 'C' then 'closed'
        when 'X' then null
        when '0' then 'no dpd'
        when '1' then 'dpd 1-30'
        when '2' then 'dpd 31-60'
        when '3' then 'dpd 61-90'
        when '4' then 'dpd 91-120'
        when '5' then 'dpd 120+ or written off'
    end                                                         as status_description,
    "_loaded_at"                                                as loaded_at,
    "_batch_id"                                                 as batch_id
from source
