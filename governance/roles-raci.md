# Roles and RACI

## Roles

| Role | Who (in a multifinance company) | Responsible for | In this project |
|---|---|---|---|
| **Data Owner** | Business head accountable for a data domain: Loan Origination (applications), Credit Risk (bureau data, scores, default flag), Collections (installments) | Decides what the data means, who may access it, which quality level is acceptable; approves exceptions and classification | `data_owner` meta on every source table and column |
| **Data Steward** | Data Governance team | Defines and maintains DQ rules, metadata and the issue log; triages failures; coordinates fixes between owner and custodian | `data_steward: Data Governance` on every column; author of `governance/` |
| **Data Custodian** | IT / Data Platform | Runs the infrastructure: loads, storage, backups, access controls, the pipeline itself | Docker Postgres, `ingestion/`, `audit.load_log`, `_loaded_at` / `_batch_id` audit columns |
| **Data Consumer** | Risk analysts, collections, management reporting, model developers | Uses data according to its classification; reports suspected issues | Marts (`dim_applicant`, `fct_loan_application`, `fct_installment`) and the DQ scorecard exposure |

Owner vs steward vs custodian in one line: the **owner decides**, the **steward defines and checks**, the **custodian operates**.

## RACI

R = Responsible (does the work), A = Accountable (final decision, one per row), C = Consulted, I = Informed.

| Activity | Data Owner | Data Steward | Data Custodian | Data Consumer |
|---|---|---|---|---|
| Define a DQ rule and its threshold | A | R | C | C |
| Classify a column (Public to Restricted) | A | R | C | I |
| Implement the rule as a dbt test | I | A | R | I |
| Fix data at source | A | C | R | I |
| Cleanse or flag in staging | C | A | R | I |
| Approve an exception (accept a known issue, downgrade to warn) | A | R | I | I |
| Monitor the scorecard and freshness | I | A / R | C | I |
| Triage a failing `error` rule | C | A / R | R | I |
| Grant access to Restricted data | A | C | R | I |
| Report a suspected data issue | I | A | I | R |

## Example: DQ-009 (orphan installments)

- **Steward** (R): found 162,149 orphan rows in profiling, wrote rule INST_PREVIOUS_EXISTS, logged DQ-009.
- **Owner** Collections (A): decides whether payments without loan terms may be used in reporting. Interim decision: keep and flag.
- **Custodian** (R): investigates whether the previous_application extract is incomplete.
- **Consumers** (I): see `is_orphan_previous_application` in `fct_installment` and filter as needed.
