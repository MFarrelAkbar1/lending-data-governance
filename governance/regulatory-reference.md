# Regulatory and Framework Reference

> **Self-study mapping, not a compliance claim.** This is a personal project on a public dataset. The notes below record how I understand the pipeline's practices relate to Indonesian regulation and to DAMA-DMBOK. They are not legal advice and have not been reviewed by a compliance or legal professional.

## POJK No. 4/POJK.05/2021 (IT risk management for non-bank financial institutions)

This OJK regulation sets IT risk management expectations for LJKNB, which include multifinance companies (perusahaan pembiayaan). Areas where this pipeline shows a related practice:

| Theme in the regulation (my reading) | Related practice in this project | Gap compared with a real implementation |
|---|---|---|
| IT risk management covers data integrity and data management | DQ rules on 6 dimensions, stored failing rows, DQ history | No formal risk register or risk appetite linked to DQ scores |
| Controls over data processing and change | Pipeline as code (dbt, git), every transformation documented in model YAML, raw kept immutable | No change approval workflow, no segregation of duties |
| Information security and access control | Column classification and PII tags | Tags are not enforced; no access control, masking or encryption implemented |
| Audit trail | `audit.load_log`, `_loaded_at`, `_batch_id`, `dq_results_history` with run ID | No tamper-proof logging, no user activity logs |
| Monitoring and reporting | Scorecard with trend across runs, source freshness | No alerting, no scheduled reporting to management |

## UU No. 27 Tahun 2022 (Pelindungan Data Pribadi)

| Topic (my reading) | Related practice | Gap |
|---|---|---|
| Specific vs general personal data | `pdp_category` meta on every column: 53 columns tagged as specific (personal financial data), 64 as general | Classification is rule-based and author-defined |
| Accuracy of personal data (controller should keep data accurate and complete) | DQ rules, cleansing, issue log; no imputation of missing personal data | No process for data subjects to correct their data |
| Data minimization | Staging and marts carry a curated subset of columns, not all 122 application columns | Raw still holds everything |
| Security of processing | Classification as the basis for handling rules | No technical controls implemented |

## DAMA-DMBOK knowledge areas covered

| Knowledge area | Where in this project |
|---|---|
| Data Governance | Roles and RACI, standards, issue log, ownership meta |
| Data Quality | Profiling, 149 dbt tests over 6 dimensions, scorecard, issue management |
| Metadata Management | dbt docs catalog: descriptions, classification, owner and steward on 187 source columns; lineage graph; exposure |
| Data Security | Classification levels and PII tags (definition only) |
| Data Integration and Interoperability | Ingestion with audit columns and load log |
| Data Modeling and Design | Staging and mart layers with documented grain |
| Data Warehousing and BI | Marts and the DQ scorecard report |

Not covered: Reference and Master Data, Document and Content Management, Data Architecture beyond a simple layered design, Data Storage and Operations beyond Docker Postgres.
