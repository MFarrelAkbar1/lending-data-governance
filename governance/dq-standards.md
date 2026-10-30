# Data Quality Standards

## Dimensions

| Dimension | Definition | Example rules in this project | Target |
|---|---|---|---|
| Completeness | Required values and rows are present | IDs, AMT_CREDIT and contract type not null; staging row count equals raw (`*_no_rows_dropped`); null share of OCCUPATION_TYPE below 20% | 0 nulls in key and critical columns; critical columns below 1% null; important columns below 20% null |
| Uniqueness | Each entity is recorded once at the documented grain | SK_ID_CURR unique; (SK_ID_BUREAU, MONTHS_BALANCE) unique; installment key unique | 0 duplicates |
| Validity | Values follow format, range and allowed lists | CODE_GENDER in (M, F); amounts >= 0; age 18 to 75; no XNA / XAP codes; no 365243 or -1 placeholders | 100% of rows valid after cleansing |
| Consistency | Values agree with each other and with conventions | AMT_ANNUITY <= AMT_CREDIT; payment at most 2x installment; DAYS_* <= 0; mart totals equal staging totals | 0 violations, or documented exceptions |
| Referential integrity | Child records point to an existing parent | bureau.SK_ID_CURR in application_train; installments.SK_ID_PREV in previous_application | 0 orphans, or documented exceptions |
| Timeliness | Data is recent enough for its use | dbt source freshness and `dbt_utils.recency` on `_loaded_at` | Warn after 1 day, error after 7 days |

## Column tiers

- **Key**: identifiers and foreign keys. Must be complete, unique (where a PK) and referentially valid.
- **Critical**: drives credit decisions or finance (credit amount, annuity, goods price, contract type). Null share below 1%.
- **Important**: used in analysis and segmentation (occupation, external scores). Null share below 20%.
- **Other**: no threshold; profiled and documented only.

## Severity

| Severity | Use for | Effect when the rule fails |
|---|---|---|
| `error` | Rules that must never fail: keys, row counts, allowed values after cleansing, sign conventions, reconciliation | `dbt test` exits non-zero and the run is treated as failed. Results are still written to `dq.dq_results_history` and failing rows to schema `dq_failures`. Downstream consumers should not use the run until fixed. |
| `warn` | Known and documented issues (each references an issue log ID), and every rule on raw data | Run continues. Failure shows on the scorecard and is tracked across runs. |

## What happens when a rule fails

1. **Detect**: `dbt test --store-failures` writes the failing rows to `dq_failures.<test_name>`; `collect_dq_results.py` appends the result to history.
2. **Triage** (Data Steward, within 1 working day for `error`): look at stored failing rows, decide whether the data or the rule is wrong (see DQ-018 for a rule that was wrong).
3. **Log**: add or update an entry in `dq-issue-log.md` with rows affected, root cause hypothesis and proposed treatment.
4. **Treat**: one of cleanse (replace value in staging, original kept in raw), flag (add a boolean, keep the row), accept (document, downgrade to `warn` with owner approval), or fix at source (request to the data custodian or upstream owner).
5. **Monitor**: the rule stays in place; the scorecard shows whether the failure count goes up or down across runs.

## Cleansing principles

- **Flag, never delete.** Rows are never dropped; `*_no_rows_dropped` tests enforce it. Deleting hides the problem from consumers and breaks reconciliation with source.
- **Placeholders and sentinels become NULL plus a flag.** 365243 in DAYS_* and -1 in SELLERPLACE_AREA mean "not applicable", not a number.
- **Unknown codes become NULL.** XNA, XAP, 'Unknown' and empty string are mapped by one macro (`clean_category`) so the rule is applied the same way everywhere.
- **No imputation of personal data.** Missing occupation or annuity stays missing.
- **Raw is immutable.** All changes happen in staging; raw keeps the source value for audit.

## DQ score

`dq_score_pct` = tests passed / tests run x 100, per table and dimension, per run (`dq_scorecard` model). A `warn` counts as not passed. The thresholds and tiers above were chosen by the author for this project, not taken from a company standard.
