{#
    Cleansing helpers used by the staging models. Rules are documented in
    governance/dq-standards.md and in the staging model YAML.
#}

{# Unknown category codes found in profiling. They all map to NULL. #}
{% macro unknown_codes() -%}
    ('XNA', 'XAP', 'UNKNOWN', '')
{%- endmacro %}

{# Trim a text column and map unknown codes (XNA, XAP, Unknown, empty) to NULL. #}
{% macro clean_category(column) -%}
    case when upper(trim({{ column }})) in {{ unknown_codes() }} then null else trim({{ column }}) end
{%- endmacro %}

{# DAYS_* placeholder: replace the value with NULL; pair with days_placeholder_flag(). #}
{% macro clean_days(column, placeholder=365243) -%}
    case when {{ column }} = {{ placeholder }} then null else {{ column }}::integer end
{%- endmacro %}

{% macro days_placeholder_flag(column, placeholder=365243) -%}
    coalesce({{ column }} = {{ placeholder }}, false)
{%- endmacro %}

{# Y/N flag to boolean. #}
{% macro yn_to_bool(column) -%}
    case upper(trim({{ column }})) when 'Y' then true when 'N' then false end
{%- endmacro %}

{# Monetary amounts are stored as double precision in raw; cast to numeric(18, 2). #}
{% macro to_amount(column) -%}
    round({{ column }}::numeric, 2)::numeric(18, 2)
{%- endmacro %}
