"""Stage 2: profile every raw table.

Writes:
    profiling/output/profile.md               readable summary
    profiling/output/<table>_columns.csv      per-column profile
    profiling/output/findings.csv             checks that feed the DQ issue log

Usage:
    python -m profiling.profile_report
"""
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from common.db import get_engine


SQL_FILE = Path(__file__).with_name("profile.sql")
OUT_DIR = Path(__file__).with_name("output")

TABLES = {
    "application_train": ["SK_ID_CURR"],
    "bureau": ["SK_ID_BUREAU"],
    "bureau_balance": ["SK_ID_BUREAU", "MONTHS_BALANCE"],
    "previous_application": ["SK_ID_PREV"],
    "installments_payments": ["SK_ID_PREV", "NUM_INSTALMENT_NUMBER", "NUM_INSTALMENT_VERSION"],
}

# (child, fk, parent, pk)
FOREIGN_KEYS = [
    ("bureau", "SK_ID_CURR", "application_train", "SK_ID_CURR"),
    ("bureau_balance", "SK_ID_BUREAU", "bureau", "SK_ID_BUREAU"),
    ("previous_application", "SK_ID_CURR", "application_train", "SK_ID_CURR"),
    ("installments_payments", "SK_ID_CURR", "application_train", "SK_ID_CURR"),
    ("installments_payments", "SK_ID_PREV", "previous_application", "SK_ID_PREV"),
]

NUMERIC_TYPES = {"bigint", "integer", "double precision", "numeric", "real", "smallint"}
TEXT_TYPES = {"text", "character varying"}

# Placeholder heuristic: an extreme value that repeats in at least 0.5% of
# non-null rows and is at least 5x the 99th percentile of the other values.
PLACEHOLDER_MIN_SHARE = 0.005
PLACEHOLDER_MIN_RATIO = 5
PLACEHOLDER_MIN_DISTINCT = 20
# DAYS_* values older than this many days (100 years) are implausible.
DAYS_MIN_PLAUSIBLE = -36_500


def load_queries() -> dict[str, str]:
    queries, name, lines = {}, None, []
    for line in SQL_FILE.read_text().splitlines():
        match = re.match(r"--\s*name:\s*(\w+)", line)
        if match:
            if name:
                queries[name] = "\n".join(lines).strip().rstrip(";")
            name, lines = match.group(1), []
        elif name and not line.startswith("--"):
            lines.append(line)
    queries[name] = "\n".join(lines).strip().rstrip(";")
    return queries


def q(identifier: str) -> str:
    return f'"{identifier}"'


def profile_table(conn, queries, table: str) -> tuple[pd.DataFrame, int]:
    columns = conn.execute(text(queries["columns"]), {"table_name": table}).fetchall()
    row_count = conn.execute(text(queries["row_count"].format(table=q(table)))).scalar()
    records = []
    for column, dtype in columns:
        stats = conn.execute(
            text(queries["column_stats"].format(table=q(table), column=q(column)))
        ).mappings().one()
        top = conn.execute(
            text(queries["top_values"].format(table=q(table), column=q(column)))
        ).fetchall()
        records.append(
            {
                "column": column,
                "data_type": dtype,
                "null_count": stats["null_count"],
                "null_pct": round(100 * stats["null_count"] / row_count, 2) if row_count else 0,
                "distinct_count": stats["distinct_count"],
                "min": stats["min_value"],
                "max": stats["max_value"],
                "top_5_values": "; ".join(f"{v} ({f:,})" for v, f in top),
            }
        )
    return pd.DataFrame(records), row_count


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    queries = load_queries()
    engine = get_engine()
    findings = []
    summaries = []
    profiles = {}

    with engine.connect() as conn:
        for table, key in TABLES.items():
            print(f"Profiling {table} ...")
            prof, row_count = profile_table(conn, queries, table)
            prof.to_csv(OUT_DIR / f"{table}_columns.csv", index=False)
            profiles[table] = (prof, row_count)

            # Primary key checks
            key_sql = ", ".join(q(k) for k in key)
            dup = conn.execute(
                text(queries["pk_duplicates"].format(table=q(table), key_columns=key_sql))
            ).mappings().one()
            nulls = conn.execute(
                text(queries["pk_nulls"].format(
                    table=q(table), null_condition=" OR ".join(f"{q(k)} IS NULL" for k in key)))
            ).scalar()
            summaries.append(
                {"table": table, "rows": row_count, "columns": len(prof),
                 "key": " + ".join(key), "duplicate_keys": dup["duplicate_keys"],
                 "rows_in_duplicate_keys": dup["rows_in_duplicate_keys"], "null_keys": nulls}
            )
            if dup["duplicate_keys"] or nulls:
                findings.append(
                    {"check": "primary_key", "table": table, "column": " + ".join(key),
                     "rows_affected": int(dup["rows_in_duplicate_keys"]) + int(nulls),
                     "pct_of_rows": round(100 * (int(dup["rows_in_duplicate_keys"]) + int(nulls)) / row_count, 2),
                     "detail": f"{dup['duplicate_keys']:,} key values repeat ({dup['rows_in_duplicate_keys']:,} rows); {nulls:,} null keys"}
                )

            # Placeholder values in numeric columns
            for _, col in prof[prof["data_type"].isin(NUMERIC_TYPES)].iterrows():
                if col["distinct_count"] < PLACEHOLDER_MIN_DISTINCT:
                    continue
                for row in conn.execute(
                    text(queries["extreme_value"].format(table=q(table), column=q(col["column"])))
                ).mappings():
                    if not row["non_null"] or row["p99_abs_others"] is None:
                        continue
                    share = row["freq"] / row["non_null"]
                    value = abs(float(row["value"]))
                    p99 = float(row["p99_abs_others"])
                    if share >= PLACEHOLDER_MIN_SHARE and value >= PLACEHOLDER_MIN_RATIO * max(p99, 1):
                        findings.append(
                            {"check": "placeholder_value", "table": table, "column": col["column"],
                             "rows_affected": int(row["freq"]),
                             "pct_of_rows": round(100 * row["freq"] / row_count, 2),
                             "detail": f"{row['side']} value {row['value']} repeats {row['freq']:,} times "
                                       f"({100 * share:.2f}% of non-null); p99 of other values is {p99:,.0f}"}
                        )

            # Rule-based numeric checks: -1 sentinel codes, negative amounts, implausible DAYS_*
            for _, col in prof[prof["data_type"].isin(NUMERIC_TYPES)].iterrows():
                name = col["column"]
                checks = conn.execute(
                    text(queries["numeric_rules"].format(table=q(table), column=q(name),
                                                         days_min=DAYS_MIN_PLAUSIBLE))
                ).mappings().one()
                if checks["minus_one"] and not checks["below_minus_one"] and col["distinct_count"] > 2:
                    findings.append(
                        {"check": "sentinel_value", "table": table, "column": name,
                         "rows_affected": int(checks["minus_one"]),
                         "pct_of_rows": round(100 * checks["minus_one"] / row_count, 2),
                         "detail": f"value -1 appears {checks['minus_one']:,} times and no other value is negative"}
                    )
                if name.startswith("AMT_") and checks["negative"]:
                    findings.append(
                        {"check": "negative_amount", "table": table, "column": name,
                         "rows_affected": int(checks["negative"]),
                         "pct_of_rows": round(100 * checks["negative"] / row_count, 2),
                         "detail": f"{checks['negative']:,} negative values, min {col['min']}"}
                    )
                if name.startswith("DAYS_") and checks["days_implausible"]:
                    findings.append(
                        {"check": "implausible_days", "table": table, "column": name,
                         "rows_affected": int(checks["days_implausible"]),
                         "pct_of_rows": round(100 * checks["days_implausible"] / row_count, 2),
                         "detail": f"{checks['days_implausible']:,} values below {DAYS_MIN_PLAUSIBLE:,} "
                                   f"(more than 100 years ago), min {col['min']}"}
                    )

            # Unknown category codes in text columns
            for _, col in prof[prof["data_type"].isin(TEXT_TYPES)].iterrows():
                for value, freq in conn.execute(
                    text(queries["unknown_codes"].format(table=q(table), column=q(col["column"])))
                ):
                    findings.append(
                        {"check": "unknown_code", "table": table, "column": col["column"],
                         "rows_affected": int(freq), "pct_of_rows": round(100 * freq / row_count, 2),
                         "detail": f"value '{value}' appears {freq:,} times"}
                    )

            # High null share (reported for awareness, threshold 50%)
            for _, col in prof[prof["null_pct"] >= 50].iterrows():
                findings.append(
                    {"check": "high_null_pct", "table": table, "column": col["column"],
                     "rows_affected": int(col["null_count"]), "pct_of_rows": col["null_pct"],
                     "detail": f"{col['null_pct']}% null"}
                )

        orphans = []
        for child, fk, parent, pk in FOREIGN_KEYS:
            res = conn.execute(
                text(queries["orphans"].format(child=q(child), fk=q(fk), parent=q(parent), pk=q(pk)))
            ).mappings().one()
            child_rows = profiles[child][1]
            orphans.append({"child": child, "fk": fk, "parent": parent, **res})
            if res["orphan_rows"]:
                findings.append(
                    {"check": "orphan_fk", "table": child, "column": fk,
                     "rows_affected": int(res["orphan_rows"]),
                     "pct_of_rows": round(100 * res["orphan_rows"] / child_rows, 2),
                     "detail": f"{res['orphan_rows']:,} rows ({res['orphan_keys']:,} distinct keys) "
                               f"have no matching {parent}.{pk}"}
                )

    findings_df = pd.DataFrame(findings)
    findings_df.to_csv(OUT_DIR / "findings.csv", index=False)
    write_markdown(summaries, orphans, findings_df, profiles)
    print(f"Wrote {OUT_DIR / 'profile.md'} with {len(findings_df)} findings")


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]).replace("|", "/") for c in cols) + " |")
    return "\n".join(lines)


def write_markdown(summaries, orphans, findings_df, profiles) -> None:
    total_rows = sum(s["rows"] for s in summaries)
    total_cols = sum(s["columns"] for s in summaries)
    out = [
        "# Raw data profile",
        "",
        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `profiling/profile_report.py`. "
        "All numbers below are computed from schema `raw`.",
        "",
        f"Profiled {len(summaries)} tables, {total_rows:,} rows and {total_cols} columns "
        "(audit columns excluded).",
        "",
        "## Tables and primary keys",
        "",
        md_table(pd.DataFrame(summaries)),
        "",
        "## Referential integrity (orphan checks)",
        "",
        md_table(pd.DataFrame(orphans)),
        "",
        "## Findings",
        "",
        "Checks: duplicate or null primary keys, orphan foreign keys, placeholder values in numeric "
        f"columns (extreme value repeated in >= {PLACEHOLDER_MIN_SHARE:.1%} of non-null rows and >= "
        f"{PLACEHOLDER_MIN_RATIO}x the p99 of other values), -1 sentinel codes, negative AMT_* values, "
        "DAYS_* values more than 100 years in the past, unknown category codes "
        "(XNA, XAP, Unknown, empty string and similar), and columns with >= 50% nulls.",
        "",
    ]
    if findings_df.empty:
        out.append("No findings.")
    else:
        main_checks = findings_df[findings_df["check"] != "high_null_pct"]
        out += [md_table(main_checks), ""]
        high_null = findings_df[findings_df["check"] == "high_null_pct"]
        if not high_null.empty:
            out += ["### Columns with >= 50% nulls", "",
                    md_table(high_null.groupby("table").agg(columns=("column", "count"),
                                                            examples=("column", lambda s: ", ".join(s.head(6))))
                             .reset_index()),
                    "", "Full list in `findings.csv`.", ""]

    out += ["## Column profiles", "",
            "Per-column data type, nulls, distinct count, min, max and top 5 values are in "
            "`<table>_columns.csv`. Highest-null columns per table:", ""]
    for table, (prof, _) in profiles.items():
        top_null = prof.sort_values("null_pct", ascending=False).head(5)
        out += [f"### {table}", "",
                md_table(top_null[["column", "data_type", "null_pct", "distinct_count", "min", "max"]]), ""]
    (OUT_DIR / "profile.md").write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    main()
