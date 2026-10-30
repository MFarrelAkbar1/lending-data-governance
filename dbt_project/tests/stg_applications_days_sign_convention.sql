{{ config(
    severity='error',
    meta={'dq_dimension': 'consistency', 'rule_id': 'APP_DAYS_SIGN_CONVENTION',
          'dq_table': 'stg_applications', 'layer': 'staging'}
) }}

-- After cleansing, every days_* column must follow the <= 0 convention.

select applicant_id, days_birth, days_employed, days_registration, days_id_publish, days_last_phone_change
from {{ ref('stg_applications') }}
where days_birth > 0
   or days_employed > 0
   or days_registration > 0
   or days_id_publish > 0
   or days_last_phone_change > 0
