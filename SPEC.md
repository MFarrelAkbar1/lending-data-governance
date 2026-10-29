# SPEC: Lending Data Quality & Governance Pipeline

Repo name suggestion: `lending-data-governance`
Owner: Muhammad Farrel Akbar
Target: finished and pushed to GitHub by 28 Oct 2026 (application deadline 31 Oct 2026)

## 1. Goal

Build a small but realistic data governance and data quality pipeline on public consumer lending data, showing the exact tasks of a Junior Data Management & Governance role at a multifinance company:

- Data profiling, validation, and cleansing
- Data quality rules and a data quality scorecard
- Metadata, data catalog, data lineage, and documentation
- Simple monitoring of data loads and data quality over time
- Governance artifacts: data classification, roles, DQ standards, issue log

Honesty rule: this is a personal project on a public dataset. Every number in the README and CV must come from actual pipeline output. No hardcoded insight text.

## 2. Dataset

Home Credit Default Risk (Kaggle competition dataset, consumer lending, multi-table).

Use these 5 tables:

| Table | Grain | Key |
|---|---|---|
| application_train | 1 row per loan application | SK_ID_CURR |
| bureau | 1 row per external credit record | SK_ID_BUREAU, FK SK_ID_CURR |
| bureau_balance | 1 row per bureau record per month | SK_ID_BUREAU + MONTHS_BALANCE |
| previous_application | 1 row per previous application | SK_ID_PREV, FK SK_ID_CURR |
| installments_payments | 1 row per installment payment | SK_ID_PREV + NUM_INSTALMENT_NUMBER + NUM_INSTALMENT_VERSION |

Sampling (to keep the laptop fast):
- Randomly sample 50,000 SK_ID_CURR from application_train with a fixed seed (42).
- Filter every child table by those IDs (bureau_balance via the sampled SK_ID_BUREAU) so referential integrity is preserved by the sampling itself.
- Do not commit raw CSVs to GitHub. Add `data/` to `.gitignore`. Document the download steps in the README (Kaggle account, accept competition rules, `kaggle competitions download -c home-credit-default-risk`).

## 3. Stack

- Python 3.11 (ingestion, sampling, report generation)
- PostgreSQL 16 in Docker (docker compose)
- dbt-core + dbt-postgres
- dbt packages: dbt_utils, dbt_expectations (metaplane fork or calogica, whichever installs cleanly)
- pandas, SQLAlchemy, Plotly (scorecard HTML report)
- Makefile or a `run.sh` with one command per stage

## 4. Repository structure

```
lending-data-governance/
  docker-compose.yml
  Makefile
  README.md
  ingestion/
    sample_and_load.py        # sample, add metadata columns, load into schema raw
  profiling/
    profile.sql               # profiling queries
    profile_report.py         # runs queries, writes profiling/output/profile.md + .csv
  dbt_project/
    dbt_project.yml
    packages.yml
    models/
      sources.yml             # raw sources, freshness, column docs, meta
      staging/                # stg_* models: cleansing and standardization
      marts/                  # dim_applicant, fct_loan_application, fct_installment
      dq/                     # dq_results, dq_scorecard models
    tests/                    # custom singular tests
    macros/
  governance/
    data-classification.md
    dq-standards.md
    roles-raci.md
    dq-issue-log.md
    regulatory-reference.md
  reports/
    build_scorecard.py        # writes reports/dq_scorecard.html
  docs/
    screenshots/              # dbt docs lineage graph, scorecard
```

## 5. Pipeline stages

### Stage 1: Ingestion (`make load`)
- Load sampled tables into schema `raw`, all columns as-is.
- Add audit columns to every raw table: `_loaded_at` (timestamp), `_source_file`, `_batch_id`.
- Write one row per table per run into `audit.load_log`: table, row count, column count, load time, duration, status.

### Stage 2: Profiling (`make profile`)
For every raw table, compute and save:
- Row count, column count
- Per column: data type, null count and null %, distinct count, min, max, top 5 values with frequency
- Primary key uniqueness check
- Orphan check for every FK (child rows whose parent key does not exist)
- Suspicious placeholder values in numeric columns (for example a single repeated extreme value in DAYS_* columns)
- Category values that look like "unknown" codes (for example XNA, XAP, empty string)

Output: `profiling/output/profile.md` (readable summary) and per-table CSVs. Findings feed the DQ issue log.

### Stage 3: Data quality rules (`make test`)
Implement dbt tests on sources and staging models, covering 6 dimensions. Every test gets `meta: {dq_dimension: ..., severity: ...}` and a description.

| Dimension | Example rules |
|---|---|
| Completeness | Key columns not null (IDs, AMT_CREDIT, AMT_ANNUITY, CONTRACT_TYPE); null % of critical columns below threshold |
| Uniqueness | SK_ID_CURR unique in applications; composite key unique in installments and bureau_balance |
| Validity | CODE_GENDER in accepted set; amounts >= 0; DAYS_BIRTH within plausible age range (18 to 75 years); categorical columns in accepted values |
| Consistency | AMT_ANNUITY <= AMT_CREDIT; AMT_PAYMENT not hugely above AMT_INSTALMENT without explanation; DAYS_* sign conventions consistent |
| Referential integrity | Every bureau.SK_ID_CURR exists in applications; every installment SK_ID_PREV exists in previous_application |
| Timeliness | dbt source freshness on `_loaded_at` (warn after 1 day, error after 7 days) |

Run tests with `--store-failures` so failing rows are kept for investigation.
Use `severity: warn` for known, documented issues and `error` for rules that must never fail.

### Stage 4: Cleansing (staging models)
- Rename to snake_case, cast types, trim strings.
- Convert DAYS_* placeholder values found in profiling to NULL plus a boolean flag column (for example `is_days_employed_placeholder`), never silently drop rows.
- Map unknown category codes to NULL or 'unknown' consistently and document the rule.
- Derive readable fields: age_years, employment_years.
- Every transformation documented in the model YAML.

### Stage 5: Marts
- `dim_applicant`: one row per applicant, cleaned demographics and income.
- `fct_loan_application`: one row per application with contract and amount fields.
- `fct_installment`: payment behavior, days late, underpayment flag.
Keep marts small; the point is governance, not modeling.

### Stage 6: DQ results and scorecard (`make scorecard`)
- After each `dbt test`, parse `target/run_results.json` and append to table `dq.dq_results_history`: run_id, run_at, test name, model, column, dimension, severity, status, failures count, rows checked.
- dbt model `dq_scorecard`: pass rate per table per dimension, overall DQ score per table, trend across runs.
- `reports/build_scorecard.py` produces `reports/dq_scorecard.html` with Plotly:
  - Overall score per table
  - Heatmap table x dimension
  - Before vs after cleansing comparison (raw-level tests vs staging-level tests)
  - Top failing rules with failure counts
- Run the pipeline at least twice so the history table shows monitoring over time.

### Stage 7: Catalog, metadata, lineage (`make docs`)
- Every source, model, and column has a description.
- Column-level `meta` on every source column:
  - `classification`: Public, Internal, Confidential, or Restricted
  - `pii`: true or false
  - `data_owner`: business role (for example "Credit Risk")
  - `data_steward`: role (for example "Data Governance")
- Model-level meta: owner, refresh frequency, upstream system.
- `dbt docs generate` gives the searchable data catalog and lineage graph. Take screenshots for the README.
- Add one dbt exposure for the scorecard report so lineage shows the consumer.

## 6. Governance documents (`governance/`)

Short and practical, 1 page each, in English:

- `data-classification.md`: 4 levels, definitions, handling rules, examples from this dataset. Note which fields would be personal data under Indonesian law (UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi), stated as a learning reference, not legal advice.
- `dq-standards.md`: the 6 dimensions, definitions, target thresholds, severity levels, and what happens when a rule fails.
- `roles-raci.md`: Data Owner, Data Steward, Data Custodian (IT), Data Consumer; RACI for define rule, fix data, approve exception, monitor.
- `dq-issue-log.md`: every issue found in profiling: ID, table, column, description, dimension, impact, rows affected, root cause hypothesis, treatment (cleansed, flagged, accepted), status.
- `regulatory-reference.md`: brief, honest notes on how this pipeline relates to POJK No. 4/POJK.05/2021 (IT risk management for non-bank financial institutions) and UU PDP, plus DAMA-DMBOK knowledge areas covered. Clearly marked as a self-study mapping, not a compliance claim.

## 7. README sections

1. One-paragraph summary (problem, what was built, stack)
2. Architecture diagram (raw, staging, marts, dq, with dbt tests and docs)
3. How to run (5 commands max)
4. Key results with real numbers from the latest run: rows profiled, rules implemented, issues found, DQ score before vs after cleansing
5. Screenshots: lineage graph, catalog page with column meta, scorecard
6. Governance artifacts list with links
7. Limitations (sampled data, static dataset so freshness is simulated via reloads, thresholds chosen by me)

## 8. Acceptance criteria

- `docker compose up -d && make all` runs end to end on a fresh clone (after placing the Kaggle CSVs in `data/`).
- At least 30 dbt tests across all 6 dimensions, each tagged with a dimension.
- Every source column has description and classification meta.
- `dq_results_history` contains at least 2 runs.
- Scorecard HTML opens and shows before vs after cleansing.
- Issue log has at least 8 real issues found by profiling, each with treatment.
- No em dashes in any document.

## 9. Plan

| Day | Work |
|---|---|
| 26 Oct | Docker Postgres, sampling and load, audit log, profiling report |
| 27 Oct | dbt sources with meta, staging cleansing, 30+ tests, store failures |
| 28 Oct | DQ history and scorecard, dbt docs and screenshots, governance docs, README, push |
| 29 Oct | Tailor CV for BRI Finance using real numbers from the README |
| 30 Oct | Apply |

## 10. Interview talking points to prepare after building

- Walk through one issue from discovery (profiling) to rule (dbt test) to treatment (cleansing) to monitoring (scorecard).
- Why flag instead of delete.
- Difference between data owner, steward, and custodian.
- How column classification connects to access control and UU PDP.
- How this would scale in a company (scheduler such as Airflow, catalog tools such as OpenMetadata or DataHub, alerting).
