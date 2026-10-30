{{ config(
    severity='warn',
    meta={'dq_dimension': 'consistency', 'rule_id': 'APP_DAYS_SIGN_CONVENTION',
          'dq_table': 'application_train', 'layer': 'raw'}
) }}

-- All DAYS_* columns of an application are relative to the application date,
-- so they must be <= 0. Fails on raw because of the 365243 placeholder (DQ-001).

select "SK_ID_CURR", "DAYS_BIRTH", "DAYS_EMPLOYED", "DAYS_REGISTRATION", "DAYS_ID_PUBLISH", "DAYS_LAST_PHONE_CHANGE"
from {{ source('raw', 'application_train') }}
where "DAYS_BIRTH" > 0
   or "DAYS_EMPLOYED" > 0
   or "DAYS_REGISTRATION" > 0
   or "DAYS_ID_PUBLISH" > 0
   or "DAYS_LAST_PHONE_CHANGE" > 0
