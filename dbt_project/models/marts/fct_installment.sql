-- One row per installment (previous application, instalment number, version).
-- Split payments from stg_installments are summed here.

with payments as (
    select
        previous_application_id,
        instalment_number,
        instalment_version,
        min(applicant_id)                                    as applicant_id,
        max(days_instalment_due)                             as days_instalment_due,
        max(instalment_amount)                               as instalment_amount,
        coalesce(sum(payment_amount), 0)                     as paid_amount,
        count(payment_amount)                                as payment_count,
        min(days_entry_payment)                              as days_first_payment,
        max(days_entry_payment)                              as days_last_payment,
        bool_or(is_overpayment)                              as has_overpayment,
        bool_or(is_orphan_previous_application)              as is_orphan_previous_application,
        max(loaded_at)                                       as loaded_at
    from {{ ref('stg_installments') }}
    group by previous_application_id, instalment_number, instalment_version
)

select
    previous_application_id,
    instalment_number,
    instalment_version,
    applicant_id,
    days_instalment_due,
    instalment_amount,
    paid_amount,
    payment_count,
    days_first_payment,
    days_last_payment,
    -- Days late = last payment day minus due day, floored at 0. NULL when nothing was paid.
    greatest(days_last_payment - days_instalment_due, 0)     as days_late,
    payment_count = 0                                        as is_unpaid,
    paid_amount < instalment_amount - 0.01                   as is_underpaid,
    has_overpayment,
    is_orphan_previous_application,
    loaded_at
from payments
