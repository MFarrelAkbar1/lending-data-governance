-- One row per applicant: cleaned demographics, employment and income.

select
    applicant_id,
    gender,
    age_years,
    family_status,
    children_count,
    family_members_count,
    education_type,
    income_type,
    occupation_type,
    organization_type,
    employment_years,
    is_days_employed_placeholder,
    housing_type,
    owns_car,
    owns_realty,
    region_rating_client,
    income_total_amount,
    loaded_at
from {{ ref('stg_applications') }}
