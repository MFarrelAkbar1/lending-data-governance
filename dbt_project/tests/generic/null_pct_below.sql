{#
    Completeness threshold test: fails (returns one row) when the share of
    null values in a column is at or above threshold_pct percent.
#}
{% test null_pct_below(model, column_name, threshold_pct) %}

with stats as (
    select
        count(*) as total_rows,
        count(*) - count({{ column_name }}) as null_rows
    from {{ model }}
)

select
    total_rows,
    null_rows,
    round(100.0 * null_rows / nullif(total_rows, 0), 2) as null_pct,
    {{ threshold_pct }} as threshold_pct
from stats
where 100.0 * null_rows / nullif(total_rows, 0) >= {{ threshold_pct }}

{% endtest %}
