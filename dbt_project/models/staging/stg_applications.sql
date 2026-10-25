-- Cleansed current loan applications. One row per application, no rows dropped.
-- Curated subset of the 122 raw columns: demographics, contract, amounts and
-- the fields used by DQ rules. Building statistics and document flags stay in raw.

with source as (
    select * from {{ source('raw', 'application_train') }}
)

select
    "SK_ID_CURR"::bigint                                        as applicant_id,
    "TARGET"::smallint                                          as target_default_flag,
    {{ clean_category('"NAME_CONTRACT_TYPE"') }}                as contract_type,
    {{ clean_category('"CODE_GENDER"') }}                       as gender,
    {{ yn_to_bool('"FLAG_OWN_CAR"') }}                          as owns_car,
    {{ yn_to_bool('"FLAG_OWN_REALTY"') }}                       as owns_realty,
    "CNT_CHILDREN"::integer                                     as children_count,
    "CNT_FAM_MEMBERS"::integer                                  as family_members_count,
    {{ clean_category('"NAME_INCOME_TYPE"') }}                  as income_type,
    {{ clean_category('"NAME_EDUCATION_TYPE"') }}               as education_type,
    {{ clean_category('"NAME_FAMILY_STATUS"') }}                as family_status,
    {{ clean_category('"NAME_HOUSING_TYPE"') }}                 as housing_type,
    {{ clean_category('"OCCUPATION_TYPE"') }}                   as occupation_type,
    {{ clean_category('"ORGANIZATION_TYPE"') }}                 as organization_type,
    {{ to_amount('"AMT_INCOME_TOTAL"') }}                       as income_total_amount,
    {{ to_amount('"AMT_CREDIT"') }}                             as credit_amount,
    {{ to_amount('"AMT_ANNUITY"') }}                            as annuity_amount,
    {{ to_amount('"AMT_GOODS_PRICE"') }}                        as goods_price_amount,
    "DAYS_BIRTH"::integer                                       as days_birth,
    floor(-"DAYS_BIRTH" / 365.25)::integer                      as age_years,
    {{ clean_days('"DAYS_EMPLOYED"') }}                         as days_employed,
    {{ days_placeholder_flag('"DAYS_EMPLOYED"') }}              as is_days_employed_placeholder,
    round((-{{ clean_days('"DAYS_EMPLOYED"') }} / 365.25)::numeric, 1) as employment_years,
    "DAYS_REGISTRATION"::integer                                as days_registration,
    "DAYS_ID_PUBLISH"::integer                                  as days_id_publish,
    "DAYS_LAST_PHONE_CHANGE"::integer                           as days_last_phone_change,
    "REGION_RATING_CLIENT"::smallint                            as region_rating_client,
    "EXT_SOURCE_1"                                              as ext_source_1,
    "EXT_SOURCE_2"                                              as ext_source_2,
    "EXT_SOURCE_3"                                              as ext_source_3,
    "_loaded_at"                                                as loaded_at,
    "_batch_id"                                                 as batch_id
from source
