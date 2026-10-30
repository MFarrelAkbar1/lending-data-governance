-- Profiling query templates used by profile_report.py.
-- Each block starts with "-- name: <query_name>". Placeholders in {braces}
-- are filled in by Python with quoted identifiers.

-- name: columns
-- Column inventory for one raw table (audit columns excluded).
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'raw'
  AND table_name = :table_name
  AND column_name NOT LIKE '\_%'
ORDER BY ordinal_position;

-- name: row_count
SELECT count(*) AS row_count FROM raw.{table};

-- name: column_stats
-- Null count, distinct count, min and max for one column.
SELECT
    count(*) - count({column})    AS null_count,
    count(DISTINCT {column})      AS distinct_count,
    min({column})::text           AS min_value,
    max({column})::text           AS max_value
FROM raw.{table};

-- name: top_values
-- Five most frequent non-null values with frequency.
SELECT {column}::text AS value, count(*) AS freq
FROM raw.{table}
WHERE {column} IS NOT NULL
GROUP BY {column}
ORDER BY freq DESC, value
LIMIT 5;

-- name: pk_duplicates
-- Key values (single or composite) that appear more than once.
SELECT count(*) AS duplicate_keys, coalesce(sum(n), 0) AS rows_in_duplicate_keys
FROM (
    SELECT count(*) AS n
    FROM raw.{table}
    GROUP BY {key_columns}
    HAVING count(*) > 1
) d;

-- name: pk_nulls
SELECT count(*) AS null_keys FROM raw.{table} WHERE {null_condition};

-- name: orphans
-- Child rows whose FK value has no matching parent key.
SELECT count(*) AS orphan_rows, count(DISTINCT c.{fk}) AS orphan_keys
FROM raw.{child} c
LEFT JOIN (SELECT DISTINCT {pk} FROM raw.{parent}) p ON c.{fk} = p.{pk}
WHERE c.{fk} IS NOT NULL
  AND p.{pk} IS NULL;

-- name: extreme_value
-- Placeholder candidate: the most frequent value at the extreme of a numeric
-- column, compared with the 99th percentile of all other values.
WITH stats AS (
    SELECT max({column}) AS max_v, min({column}) AS min_v, count({column}) AS non_null
    FROM raw.{table}
),
candidates AS (
    SELECT 'max' AS side, max_v AS value, (SELECT count(*) FROM raw.{table} WHERE {column} = max_v) AS freq, non_null FROM stats
    UNION ALL
    SELECT 'min', min_v, (SELECT count(*) FROM raw.{table} WHERE {column} = min_v), non_null FROM stats
)
SELECT
    c.side,
    c.value::text AS value,
    c.freq,
    c.non_null,
    (SELECT percentile_cont(0.99) WITHIN GROUP (ORDER BY abs({column}))
       FROM raw.{table} WHERE {column} <> c.value) AS p99_abs_others
FROM candidates c;

-- name: unknown_codes
-- Category values that look like "unknown" or "not applicable" codes.
SELECT {column} AS value, count(*) AS freq
FROM raw.{table}
WHERE upper(trim({column})) IN ('XNA', 'XAP', 'UNKNOWN', 'N/A', 'NA', 'NULL', 'NONE', '')
GROUP BY {column}
ORDER BY freq DESC;

-- name: numeric_rules
-- Counts used for rule-based numeric checks on one column.
SELECT
    count(*) FILTER (WHERE {column} = -1)          AS minus_one,
    count(*) FILTER (WHERE {column} < -1)          AS below_minus_one,
    count(*) FILTER (WHERE {column} < 0)           AS negative,
    count(*) FILTER (WHERE {column} < {days_min})  AS days_implausible
FROM raw.{table};
