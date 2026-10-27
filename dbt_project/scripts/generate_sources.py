"""Generate models/sources.yml from the live raw schema and the Kaggle data dictionary.

Why generated: the 5 raw tables have 187 columns. Descriptions come from
data/HomeCredit_columns_description.csv, governance metadata (classification,
pii, owner, steward) comes from the rules below, and raw-level DQ tests are
declared in RAW_TESTS. Editing this file and re-running it keeps the catalog
consistent instead of hand-editing a 2,000+ line YAML file.

Usage (from repo root):
    python dbt_project/scripts/generate_sources.py
"""
import re
import sys
from pathlib import Path

import pandas as pd
import yaml
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common.db import get_engine  # noqa: E402

DICTIONARY = Path("data/HomeCredit_columns_description.csv")
OUT = Path("dbt_project/models/sources.yml")

DICT_TABLE = {
    "application_train": "application_{train|test}.csv",
    "bureau": "bureau.csv",
    "bureau_balance": "bureau_balance.csv",
    "previous_application": "previous_application.csv",
    "installments_payments": "installments_payments.csv",
}

# Column names that are spelled differently in the Kaggle dictionary (see issue log DQ-015).
# The dictionary also has trailing spaces in some names ("SK_ID_PREV "), handled by strip().
DICT_ALIASES = {
    ("bureau", "SK_ID_BUREAU"): "SK_BUREAU_ID",
    ("bureau_balance", "SK_ID_BUREAU"): "SK_BUREAU_ID",
}

TABLE_META = {
    "application_train": {
        "description": "Current loan applications, one row per application (SK_ID_CURR). "
                       "Sampled: 50,000 applications drawn with seed 42.",
        "data_owner": "Loan Origination",
        "grain": "SK_ID_CURR",
    },
    "bureau": {
        "description": "Credits reported by other financial institutions to the credit bureau, "
                       "one row per bureau credit (SK_ID_BUREAU) for sampled applicants.",
        "data_owner": "Credit Risk",
        "grain": "SK_ID_BUREAU",
    },
    "bureau_balance": {
        "description": "Monthly status of each credit bureau record, one row per SK_ID_BUREAU and MONTHS_BALANCE.",
        "data_owner": "Credit Risk",
        "grain": "SK_ID_BUREAU + MONTHS_BALANCE",
    },
    "previous_application": {
        "description": "Previous Home Credit applications of sampled applicants, one row per SK_ID_PREV.",
        "data_owner": "Loan Origination",
        "grain": "SK_ID_PREV",
    },
    "installments_payments": {
        "description": "Repayment history of previous Home Credit credits. Intended grain is one row per "
                       "SK_ID_PREV + NUM_INSTALMENT_NUMBER + NUM_INSTALMENT_VERSION, but split payments "
                       "create several rows per installment (see issue log DQ-007).",
        "data_owner": "Collections",
        "grain": "SK_ID_PREV + NUM_INSTALMENT_NUMBER + NUM_INSTALMENT_VERSION (+ payment)",
    },
}

AUDIT_COLUMNS = {
    "_loaded_at": "Timestamp (UTC) when the row was loaded into schema raw by ingestion/sample_and_load.py.",
    "_source_file": "Source CSV file the row was read from.",
    "_batch_id": "Identifier of the load batch; joins to audit.load_log.batch_id.",
}

# Application columns describing a natural person (general personal data under UU PDP).
PERSONAL_ATTRIBUTES = {
    "CODE_GENDER", "DAYS_BIRTH", "CNT_CHILDREN", "CNT_FAM_MEMBERS", "NAME_FAMILY_STATUS",
    "NAME_EDUCATION_TYPE", "NAME_INCOME_TYPE", "OCCUPATION_TYPE", "ORGANIZATION_TYPE",
    "DAYS_EMPLOYED", "DAYS_REGISTRATION", "DAYS_ID_PUBLISH", "DAYS_LAST_PHONE_CHANGE",
    "FLAG_OWN_CAR", "FLAG_OWN_REALTY", "OWN_CAR_AGE", "NAME_HOUSING_TYPE", "NAME_TYPE_SUITE",
    "FLAG_MOBIL", "FLAG_EMP_PHONE", "FLAG_WORK_PHONE", "FLAG_CONT_MOBILE", "FLAG_PHONE", "FLAG_EMAIL",
    "REGION_POPULATION_RELATIVE", "REGION_RATING_CLIENT", "REGION_RATING_CLIENT_W_CITY",
    "REG_REGION_NOT_LIVE_REGION", "REG_REGION_NOT_WORK_REGION", "LIVE_REGION_NOT_WORK_REGION",
    "REG_CITY_NOT_LIVE_CITY", "REG_CITY_NOT_WORK_CITY", "LIVE_CITY_NOT_WORK_CITY",
}
# Previous-application columns that describe the credit decision or financial terms.
PREV_FINANCIAL = {"NAME_CONTRACT_STATUS", "CODE_REJECT_REASON", "CNT_PAYMENT", "NAME_YIELD_GROUP"}


def classify(table: str, column: str) -> dict:
    """Return classification meta for one column. Rules are documented in governance/data-classification.md."""
    owner = TABLE_META[table]["data_owner"]
    if column in AUDIT_COLUMNS:
        return dict(classification="Internal", pii=False, pdp_category="none",
                    data_owner="Data Platform", data_steward="Data Governance")
    if column.startswith("SK_ID_"):
        return dict(classification="Confidential", pii=True, pdp_category="general (pseudonymous identifier)",
                    data_owner=owner, data_steward="Data Governance")

    restricted = (
        table in ("bureau", "bureau_balance", "installments_payments")
        or column.startswith(("AMT_", "RATE_", "EXT_SOURCE_", "OBS_", "DEF_"))
        or column == "TARGET"
        or (table == "previous_application" and column in PREV_FINANCIAL)
    )
    if restricted:
        if column == "TARGET" or column.startswith("EXT_SOURCE_"):
            owner = "Credit Risk"
        return dict(classification="Restricted", pii=True, pdp_category="specific (personal financial data)",
                    data_owner=owner, data_steward="Data Governance")
    if table == "application_train" and column in PERSONAL_ATTRIBUTES:
        return dict(classification="Confidential", pii=True, pdp_category="general",
                    data_owner=owner, data_steward="Data Governance")
    if table == "previous_application":
        # Process and product attributes of a person's past application.
        return dict(classification="Confidential", pii=True, pdp_category="general",
                    data_owner=owner, data_steward="Data Governance")
    # Remaining application columns: normalized building statistics, document flags, process timing.
    return dict(classification="Internal", pii=False, pdp_category="none",
                data_owner=owner, data_steward="Data Governance")


def test(kind: str, name: str, dimension: str, severity: str, rule_id: str, description: str, **args) -> dict:
    where = args.pop("config_where", None)
    body = {"name": name, "description": description}
    if args:
        body["arguments"] = args
    body["config"] = {"severity": severity, "meta": {"dq_dimension": dimension, "rule_id": rule_id}}
    if where:
        body["config"]["where"] = where
    return {kind: body}


def between(name, dim, sev, rule, desc, **bounds):
    return test("dbt_expectations.expect_column_values_to_be_between", name, dim, sev, rule, desc, **bounds)


def recency(table):
    return test("dbt_utils.recency", f"raw_{table}__recency", "timeliness", "warn", f"{table.upper()}_FRESH",
                "Latest _loaded_at is within the last day.", datepart="day", field="_loaded_at", interval=1)


def rel(name, dim, sev, rule, desc, parent, field):
    return test("relationships", name, dim, sev, rule, desc, to=f"source('raw', '{parent}')", field=f'"{field}"')


# Raw-level tests. Severity warn = known, documented issue (issue log); error = must never fail.
TABLE_TESTS = {
    "application_train": [
        test("dbt_expectations.expect_table_row_count_to_equal", "raw_application_train__row_count",
             "completeness", "error", "APP_ROW_COUNT", "Sampled table holds exactly 50,000 applications.",
             value=50000),
        test("dbt_utils.expression_is_true", "raw_application_train__annuity_le_credit", "consistency", "error",
             "APP_ANNUITY_LE_CREDIT", "Annuity can never exceed the total credit amount.",
             expression='"AMT_ANNUITY" <= "AMT_CREDIT"'),
        recency("application_train"),
    ],
    "bureau": [
        test("dbt_utils.expression_is_true", "raw_bureau__enddate_fact_after_start", "consistency", "warn",
             "BUR_CLOSED_AFTER_OPENED", "A credit cannot be closed before it was opened (DQ-012).",
             expression='"DAYS_ENDDATE_FACT" >= "DAYS_CREDIT"'),
        recency("bureau"),
    ],
    "bureau_balance": [
        test("dbt_utils.unique_combination_of_columns", "raw_bureau_balance__key_unique", "uniqueness", "error",
             "BB_KEY_UNIQUE", "One row per bureau credit per month.",
             combination_of_columns=['"SK_ID_BUREAU"', '"MONTHS_BALANCE"']),
        recency("bureau_balance"),
    ],
    "previous_application": [
        test("dbt_utils.expression_is_true", "raw_previous_application__annuity_le_credit", "consistency",
             "error", "PREV_ANNUITY_LE_CREDIT", "Annuity can never exceed the credit amount when credit > 0.",
             expression='"AMT_ANNUITY" <= "AMT_CREDIT"', config_where='"AMT_CREDIT" > 0'),
        recency("previous_application"),
    ],
    "installments_payments": [
        test("dbt_utils.unique_combination_of_columns", "raw_installments_payments__key_unique", "uniqueness",
             "warn", "INST_KEY_UNIQUE", "One row per installment; fails because of split payments (DQ-007).",
             combination_of_columns=['"SK_ID_PREV"', '"NUM_INSTALMENT_NUMBER"', '"NUM_INSTALMENT_VERSION"']),
        test("dbt_utils.expression_is_true", "raw_installments_payments__payment_not_hugely_above_instalment",
             "consistency", "warn", "INST_PAYMENT_LE_2X_INSTALMENT",
             "Payment is at most 2x the installment amount (DQ-014).",
             expression='not ("AMT_INSTALMENT" > 0 and "AMT_PAYMENT" > 2 * "AMT_INSTALMENT")'),
        recency("installments_payments"),
    ],
}

NOT_POSITIVE = dict(max_value=0)

COLUMN_TESTS = {
    "application_train": {
        "SK_ID_CURR": [
            test("unique", "raw_application_train__id_unique", "uniqueness", "error", "APP_ID_UNIQUE",
                 "Application ID is unique."),
            test("not_null", "raw_application_train__id_not_null", "completeness", "error", "APP_ID_NOT_NULL",
                 "Application ID is always present."),
        ],
        "NAME_CONTRACT_TYPE": [
            test("not_null", "raw_application_train__contract_type_not_null", "completeness", "error",
                 "APP_CONTRACT_TYPE_NOT_NULL", "Contract type is always present."),
            test("accepted_values", "raw_application_train__contract_type_valid", "validity", "error",
                 "APP_CONTRACT_TYPE_VALID", "Contract type is a known product.",
                 values=["Cash loans", "Revolving loans"]),
        ],
        "CODE_GENDER": [
            test("accepted_values", "raw_application_train__gender_valid", "validity", "warn",
                 "APP_GENDER_VALID", "Gender is M or F; XNA is an unknown code (DQ-003).", values=["M", "F"]),
        ],
        "NAME_FAMILY_STATUS": [
            test("accepted_values", "raw_application_train__family_status_valid", "validity", "warn",
                 "APP_FAMILY_STATUS_VALID", "Family status is a known value; 'Unknown' is an unknown code (DQ-004).",
                 values=["Civil marriage", "Married", "Separated", "Single / not married", "Widow"]),
        ],
        "ORGANIZATION_TYPE": [
            test("dbt_expectations.expect_column_values_to_not_be_in_set", "raw_application_train__organization_no_xna",
                 "validity", "warn", "APP_ORG_NO_UNKNOWN_CODE", "Organization type does not use the XNA code (DQ-002).",
                 value_set=["XNA"]),
        ],
        "OCCUPATION_TYPE": [
            test("null_pct_below", "raw_application_train__occupation_null_pct", "completeness", "warn",
                 "APP_OCCUPATION_NULL_PCT", "Important column: null share must stay below 20% (DQ-016).",
                 threshold_pct=20),
        ],
        "AMT_CREDIT": [
            test("not_null", "raw_application_train__credit_not_null", "completeness", "error",
                 "APP_CREDIT_NOT_NULL", "Credit amount is always present."),
            between("raw_application_train__credit_positive", "validity", "error", "APP_CREDIT_POSITIVE",
                    "Credit amount is greater than zero.", min_value=0, strictly=True),
        ],
        "AMT_ANNUITY": [
            test("not_null", "raw_application_train__annuity_not_null", "completeness", "warn",
                 "APP_ANNUITY_NOT_NULL", "Annuity is present; a few rows are missing it (DQ-017)."),
        ],
        "AMT_GOODS_PRICE": [
            test("null_pct_below", "raw_application_train__goods_price_null_pct", "completeness", "error",
                 "APP_GOODS_PRICE_NULL_PCT", "Critical column: null share must stay below 1%.", threshold_pct=1),
        ],
        "AMT_INCOME_TOTAL": [
            between("raw_application_train__income_positive", "validity", "error", "APP_INCOME_POSITIVE",
                    "Income is greater than zero.", min_value=0, strictly=True),
        ],
        "DAYS_BIRTH": [
            between("raw_application_train__age_range", "validity", "error", "APP_AGE_RANGE",
                    "Applicant age is between 18 and 75 years (DAYS_BIRTH between -27,394 and -6,575).",
                    min_value=-27394, max_value=-6575),
        ],
        "DAYS_EMPLOYED": [
            between("raw_application_train__days_employed_sign", "validity", "warn", "APP_DAYS_EMPLOYED_VALID",
                    "Employment start is in the past (<= 0); 365243 is a placeholder (DQ-001).", **NOT_POSITIVE),
        ],
        "DAYS_REGISTRATION": [
            between("raw_application_train__days_registration_sign", "consistency", "error",
                    "APP_DAYS_REGISTRATION_SIGN", "DAYS_* columns relative to application are <= 0.", **NOT_POSITIVE),
        ],
        "DAYS_ID_PUBLISH": [
            between("raw_application_train__days_id_publish_sign", "consistency", "error",
                    "APP_DAYS_ID_PUBLISH_SIGN", "DAYS_* columns relative to application are <= 0.", **NOT_POSITIVE),
        ],
        "DAYS_LAST_PHONE_CHANGE": [
            between("raw_application_train__days_phone_change_sign", "consistency", "error",
                    "APP_DAYS_PHONE_CHANGE_SIGN", "DAYS_* columns relative to application are <= 0.", **NOT_POSITIVE),
        ],
    },
    "bureau": {
        "SK_ID_BUREAU": [
            test("unique", "raw_bureau__id_unique", "uniqueness", "error", "BUR_ID_UNIQUE", "Bureau credit ID is unique."),
            test("not_null", "raw_bureau__id_not_null", "completeness", "error", "BUR_ID_NOT_NULL",
                 "Bureau credit ID is always present."),
        ],
        "SK_ID_CURR": [
            rel("raw_bureau__applicant_exists", "referential_integrity", "error", "BUR_APPLICANT_EXISTS",
                "Every bureau credit belongs to an application in application_train.", "application_train",
                "SK_ID_CURR"),
        ],
        "CREDIT_ACTIVE": [
            test("accepted_values", "raw_bureau__credit_active_valid", "validity", "error", "BUR_STATUS_VALID",
                 "Bureau credit status is a known value.", values=["Active", "Closed", "Sold", "Bad debt"]),
        ],
        "AMT_CREDIT_SUM_DEBT": [
            between("raw_bureau__debt_non_negative", "validity", "warn", "BUR_DEBT_NON_NEGATIVE",
                    "Outstanding debt is not negative (DQ-010).", min_value=0),
        ],
        "AMT_CREDIT_SUM_LIMIT": [
            between("raw_bureau__limit_non_negative", "validity", "warn", "BUR_LIMIT_NON_NEGATIVE",
                    "Credit card limit is not negative (DQ-010).", min_value=0),
        ],
        "DAYS_CREDIT": [
            between("raw_bureau__days_credit_sign", "consistency", "error", "BUR_DAYS_CREDIT_SIGN",
                    "Credit was opened before the application (<= 0).", **NOT_POSITIVE),
        ],
        "DAYS_CREDIT_ENDDATE": [
            between("raw_bureau__enddate_plausible", "validity", "warn", "BUR_ENDDATE_PLAUSIBLE",
                    "Planned end date is not more than 100 years in the past (DQ-011).", min_value=-36500),
        ],
        "DAYS_CREDIT_UPDATE": [
            between("raw_bureau__update_plausible", "validity", "warn", "BUR_UPDATE_PLAUSIBLE",
                    "Last update is not more than 100 years in the past (DQ-011).", min_value=-36500),
        ],
    },
    "bureau_balance": {
        "SK_ID_BUREAU": [
            rel("raw_bureau_balance__bureau_exists", "referential_integrity", "error", "BB_BUREAU_EXISTS",
                "Every monthly balance belongs to a bureau credit.", "bureau", "SK_ID_BUREAU"),
        ],
        "STATUS": [
            test("accepted_values", "raw_bureau_balance__status_valid", "validity", "error", "BB_STATUS_VALID",
                 "Status is a DPD bucket (0 to 5), C (closed) or X (unknown).",
                 values=["0", "1", "2", "3", "4", "5", "C", "X"]),
        ],
        "MONTHS_BALANCE": [
            between("raw_bureau_balance__months_sign", "consistency", "error", "BB_MONTHS_SIGN",
                    "Month is relative to the application date and is <= 0.", **NOT_POSITIVE),
        ],
    },
    "previous_application": {
        "SK_ID_PREV": [
            test("unique", "raw_previous_application__id_unique", "uniqueness", "error", "PREV_ID_UNIQUE",
                 "Previous application ID is unique."),
            test("not_null", "raw_previous_application__id_not_null", "completeness", "error", "PREV_ID_NOT_NULL",
                 "Previous application ID is always present."),
        ],
        "SK_ID_CURR": [
            rel("raw_previous_application__applicant_exists", "referential_integrity", "error",
                "PREV_APPLICANT_EXISTS", "Every previous application belongs to an application in application_train.",
                "application_train", "SK_ID_CURR"),
        ],
        "NAME_CONTRACT_STATUS": [
            test("accepted_values", "raw_previous_application__status_valid", "validity", "error",
                 "PREV_STATUS_VALID", "Decision status is a known value.",
                 values=["Approved", "Canceled", "Refused", "Unused offer"]),
        ],
        "NAME_CONTRACT_TYPE": [
            test("accepted_values", "raw_previous_application__contract_type_valid", "validity", "warn",
                 "PREV_CONTRACT_TYPE_VALID", "Contract type is a known product; XNA is an unknown code (DQ-006).",
                 values=["Cash loans", "Consumer loans", "Revolving loans"]),
        ],
        "NAME_CASH_LOAN_PURPOSE": [
            test("dbt_expectations.expect_column_values_to_not_be_in_set",
                 "raw_previous_application__loan_purpose_no_unknown", "validity", "warn",
                 "PREV_PURPOSE_NO_UNKNOWN_CODE", "Loan purpose does not use XNA or XAP codes (DQ-006).",
                 value_set=["XNA", "XAP"]),
        ],
        "NAME_PAYMENT_TYPE": [
            test("dbt_expectations.expect_column_values_to_not_be_in_set",
                 "raw_previous_application__payment_type_no_unknown", "validity", "warn",
                 "PREV_PAYMENT_TYPE_NO_UNKNOWN_CODE", "Payment type does not use the XNA code (DQ-006).",
                 value_set=["XNA"]),
        ],
        "SELLERPLACE_AREA": [
            test("dbt_expectations.expect_column_values_to_not_be_in_set",
                 "raw_previous_application__sellerplace_no_sentinel", "validity", "warn",
                 "PREV_SELLERPLACE_NO_SENTINEL", "Seller area does not use the -1 sentinel (DQ-008).",
                 value_set=[-1], quote_values=False),
        ],
        "AMT_APPLICATION": [
            between("raw_previous_application__amount_non_negative", "validity", "error",
                    "PREV_AMOUNT_NON_NEGATIVE", "Requested amount is not negative.", min_value=0),
        ],
        "DAYS_DECISION": [
            between("raw_previous_application__days_decision_sign", "consistency", "error",
                    "PREV_DAYS_DECISION_SIGN", "Decision happened before the current application (<= 0).",
                    **NOT_POSITIVE),
        ],
        **{
            col: [between(f"raw_previous_application__{col.lower()}_valid", "validity", "warn",
                          f"PREV_{col}_VALID", f"{col} is <= 0; 365243 is a placeholder (DQ-005).", **NOT_POSITIVE)]
            for col in ("DAYS_FIRST_DRAWING", "DAYS_FIRST_DUE", "DAYS_LAST_DUE", "DAYS_TERMINATION")
        },
        # The first planned last-due date can legitimately be after the current application,
        # so this column only gets a plausibility window that still catches 365243 (DQ-018).
        "DAYS_LAST_DUE_1ST_VERSION": [
            between("raw_previous_application__days_last_due_1st_version_valid", "validity", "warn",
                    "PREV_DAYS_LAST_DUE_1ST_VERSION_VALID",
                    "Value is within +/- 100 years; 365243 is a placeholder (DQ-005, DQ-018).",
                    min_value=-36500, max_value=36500),
        ],
    },
    "installments_payments": {
        "SK_ID_PREV": [
            rel("raw_installments_payments__previous_exists", "referential_integrity", "warn",
                "INST_PREVIOUS_EXISTS", "Every installment belongs to a previous application (DQ-009).",
                "previous_application", "SK_ID_PREV"),
        ],
        "SK_ID_CURR": [
            rel("raw_installments_payments__applicant_exists", "referential_integrity", "error",
                "INST_APPLICANT_EXISTS", "Every installment belongs to an application in application_train.",
                "application_train", "SK_ID_CURR"),
        ],
        "AMT_PAYMENT": [
            test("not_null", "raw_installments_payments__payment_not_null", "completeness", "warn",
                 "INST_PAYMENT_NOT_NULL", "Payment amount is present; missing rows are unpaid installments (DQ-013)."),
            between("raw_installments_payments__payment_non_negative", "validity", "error",
                    "INST_PAYMENT_NON_NEGATIVE", "Payment amount is not negative.", min_value=0),
        ],
        "DAYS_ENTRY_PAYMENT": [
            test("not_null", "raw_installments_payments__entry_date_not_null", "completeness", "warn",
                 "INST_ENTRY_DATE_NOT_NULL", "Payment date is present; missing rows are unpaid installments (DQ-013)."),
            between("raw_installments_payments__entry_date_sign", "consistency", "error", "INST_ENTRY_DATE_SIGN",
                    "Payment happened before the current application (<= 0).", **NOT_POSITIVE),
        ],
        "AMT_INSTALMENT": [
            between("raw_installments_payments__instalment_non_negative", "validity", "error",
                    "INST_INSTALMENT_NON_NEGATIVE", "Installment amount is not negative.", min_value=0),
        ],
        "DAYS_INSTALMENT": [
            between("raw_installments_payments__due_date_sign", "consistency", "error", "INST_DUE_DATE_SIGN",
                    "Due date is before the current application (<= 0).", **NOT_POSITIVE),
        ],
    },
}


def clean(text_value: str) -> str:
    text_value = re.sub(r"\s+", " ", str(text_value)).strip()
    return text_value.encode("ascii", "ignore").decode()


def main() -> None:
    dictionary = pd.read_csv(DICTIONARY, encoding="latin-1")
    dictionary["Row"] = dictionary["Row"].str.strip()
    engine = get_engine()
    tables = []
    with engine.connect() as conn:
        for table, meta in TABLE_META.items():
            cols = conn.execute(
                text("SELECT column_name FROM information_schema.columns "
                     "WHERE table_schema = 'raw' AND table_name = :t ORDER BY ordinal_position"),
                {"t": table},
            ).scalars().all()
            d = dictionary[dictionary["Table"] == DICT_TABLE[table]].set_index("Row")
            columns = []
            for col in cols:
                if col in AUDIT_COLUMNS:
                    desc = AUDIT_COLUMNS[col]
                else:
                    key = DICT_ALIASES.get((table, col), col)
                    row = d.loc[key] if key in d.index else None
                    desc = clean(row["Description"]) if row is not None else f"{col} (no description in source dictionary)."
                    if row is not None and isinstance(row["Special"], str) and row["Special"].strip():
                        desc += f" [source note: {row['Special'].strip()}]"
                entry = {"name": col, "description": desc, "quote": True, "meta": classify(table, col)}
                tests = COLUMN_TESTS.get(table, {}).get(col, [])
                if tests:
                    entry["data_tests"] = tests
                columns.append(entry)
            tables.append({
                "name": table,
                "description": meta["description"],
                "meta": {"data_owner": meta["data_owner"], "data_steward": "Data Governance",
                         "upstream_system": "Home Credit (Kaggle extract)", "grain": meta["grain"],
                         "refresh_frequency": "on reload (simulated daily)"},
                "data_tests": TABLE_TESTS[table],
                "columns": columns,
            })

    doc = {
        "version": 2,
        "sources": [
            {
                "name": "raw",
                "description": "Sampled Home Credit Default Risk tables loaded as-is by ingestion/sample_and_load.py.",
                "schema": "raw",
                "loaded_at_field": "_loaded_at",
                "freshness": {"warn_after": {"count": 1, "period": "day"},
                              "error_after": {"count": 7, "period": "day"}},
                "quoting": {"identifier": True},
                "tables": tables,
            },
            {
                "name": "dq",
                "description": "Data quality monitoring tables written by reports/collect_dq_results.py.",
                "schema": "dq",
                "tables": [{
                    "name": "dq_results_history",
                    "description": "One row per dbt test per run, appended after every `dbt test`.",
                    "meta": {"data_owner": "Data Governance", "data_steward": "Data Governance",
                             "upstream_system": "dbt run_results.json"},
                }],
            },
            {
                "name": "audit",
                "description": "Load audit tables written by ingestion/sample_and_load.py.",
                "schema": "audit",
                "tables": [{
                    "name": "load_log",
                    "description": "One row per raw table per load run: row count, column count, duration, status.",
                    "meta": {"data_owner": "Data Platform", "data_steward": "Data Governance",
                             "upstream_system": "ingestion/sample_and_load.py"},
                }],
            },
        ],
    }

    header = ("# GENERATED by dbt_project/scripts/generate_sources.py. Do not edit by hand.\n"
              "# Descriptions: Kaggle HomeCredit_columns_description.csv. Meta: classification rules in the script.\n")
    OUT.write_text(header + yaml.safe_dump(doc, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
    n_cols = sum(len(t["columns"]) for t in tables)
    print(f"Wrote {OUT}: {len(tables)} tables, {n_cols} columns")


if __name__ == "__main__":
    main()
