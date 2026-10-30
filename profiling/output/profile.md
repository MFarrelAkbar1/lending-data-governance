# Raw data profile

Generated 2026-10-25 15:10 UTC by `profiling/profile_report.py`. All numbers below are computed from schema `raw`.

Profiled 5 tables, 4,782,142 rows and 187 columns (audit columns excluded).

## Tables and primary keys

| table | rows | columns | key | duplicate_keys | rows_in_duplicate_keys | null_keys |
|---|---|---|---|---|---|---|
| application_train | 50000 | 122 | SK_ID_CURR | 0 | 0 | 0 |
| bureau | 237076 | 17 | SK_ID_BUREAU | 0 | 0 | 0 |
| bureau_balance | 2383470 | 3 | SK_ID_BUREAU + MONTHS_BALANCE | 0 | 0 | 0 |
| previous_application | 229715 | 37 | SK_ID_PREV | 0 | 0 | 0 |
| installments_payments | 1881881 | 8 | SK_ID_PREV + NUM_INSTALMENT_NUMBER + NUM_INSTALMENT_VERSION | 89539 | 180925 | 0 |

## Referential integrity (orphan checks)

| child | fk | parent | orphan_rows | orphan_keys |
|---|---|---|---|---|
| bureau | SK_ID_CURR | application_train | 0 | 0 |
| bureau_balance | SK_ID_BUREAU | bureau | 0 | 0 |
| previous_application | SK_ID_CURR | application_train | 0 | 0 |
| installments_payments | SK_ID_CURR | application_train | 0 | 0 |
| installments_payments | SK_ID_PREV | previous_application | 162149 | 5310 |

## Findings

Checks: duplicate or null primary keys, orphan foreign keys, placeholder values in numeric columns (extreme value repeated in >= 0.5% of non-null rows and >= 5x the p99 of other values), -1 sentinel codes, negative AMT_* values, DAYS_* values more than 100 years in the past, unknown category codes (XNA, XAP, Unknown, empty string and similar), and columns with >= 50% nulls.

| check | table | column | rows_affected | pct_of_rows | detail |
|---|---|---|---|---|---|
| placeholder_value | application_train | DAYS_EMPLOYED | 8996 | 17.99 | max value 365243 repeats 8,996 times (17.99% of non-null); p99 of other values is 11,305 |
| unknown_code | application_train | CODE_GENDER | 1 | 0.0 | value 'XNA' appears 1 times |
| unknown_code | application_train | NAME_FAMILY_STATUS | 1 | 0.0 | value 'Unknown' appears 1 times |
| unknown_code | application_train | ORGANIZATION_TYPE | 8996 | 17.99 | value 'XNA' appears 8,996 times |
| implausible_days | bureau | DAYS_CREDIT_ENDDATE | 20 | 0.01 | 20 values below -36,500 (more than 100 years ago), min -42041 |
| negative_amount | bureau | AMT_CREDIT_SUM_DEBT | 1356 | 0.57 | 1,356 negative values, min -1354875.615 |
| negative_amount | bureau | AMT_CREDIT_SUM_LIMIT | 56 | 0.02 | 56 negative values, min -121905.675 |
| implausible_days | bureau | DAYS_CREDIT_UPDATE | 21 | 0.01 | 21 values below -36,500 (more than 100 years ago), min -41943 |
| placeholder_value | previous_application | DAYS_FIRST_DRAWING | 129988 | 56.59 | max value 365243 repeats 129,988 times (93.70% of non-null); p99 of other values is 2,869 |
| placeholder_value | previous_application | DAYS_FIRST_DUE | 5516 | 2.4 | max value 365243 repeats 5,516 times (3.98% of non-null); p99 of other values is 2,821 |
| placeholder_value | previous_application | DAYS_LAST_DUE_1ST_VERSION | 12874 | 5.6 | max value 365243 repeats 12,874 times (9.28% of non-null); p99 of other values is 2,609 |
| placeholder_value | previous_application | DAYS_LAST_DUE | 29454 | 12.82 | max value 365243 repeats 29,454 times (21.23% of non-null); p99 of other values is 2,644 |
| placeholder_value | previous_application | DAYS_TERMINATION | 31603 | 13.76 | max value 365243 repeats 31,603 times (22.78% of non-null); p99 of other values is 2,602 |
| sentinel_value | previous_application | SELLERPLACE_AREA | 102451 | 44.6 | value -1 appears 102,451 times and no other value is negative |
| unknown_code | previous_application | NAME_CONTRACT_TYPE | 59 | 0.03 | value 'XNA' appears 59 times |
| unknown_code | previous_application | NAME_CASH_LOAN_PURPOSE | 128773 | 56.06 | value 'XAP' appears 128,773 times |
| unknown_code | previous_application | NAME_CASH_LOAN_PURPOSE | 91270 | 39.73 | value 'XNA' appears 91,270 times |
| unknown_code | previous_application | NAME_PAYMENT_TYPE | 84798 | 36.91 | value 'XNA' appears 84,798 times |
| unknown_code | previous_application | CODE_REJECT_REASON | 186096 | 81.01 | value 'XAP' appears 186,096 times |
| unknown_code | previous_application | CODE_REJECT_REASON | 713 | 0.31 | value 'XNA' appears 713 times |
| unknown_code | previous_application | NAME_CLIENT_TYPE | 256 | 0.11 | value 'XNA' appears 256 times |
| unknown_code | previous_application | NAME_GOODS_CATEGORY | 128935 | 56.13 | value 'XNA' appears 128,935 times |
| unknown_code | previous_application | NAME_PORTFOLIO | 49825 | 21.69 | value 'XNA' appears 49,825 times |
| unknown_code | previous_application | NAME_PRODUCT_TYPE | 146765 | 63.89 | value 'XNA' appears 146,765 times |
| unknown_code | previous_application | NAME_SELLER_INDUSTRY | 115764 | 50.39 | value 'XNA' appears 115,764 times |
| unknown_code | previous_application | NAME_YIELD_GROUP | 69686 | 30.34 | value 'XNA' appears 69,686 times |
| primary_key | installments_payments | SK_ID_PREV + NUM_INSTALMENT_NUMBER + NUM_INSTALMENT_VERSION | 180925 | 9.61 | 89,539 key values repeat (180,925 rows); 0 null keys |
| orphan_fk | installments_payments | SK_ID_PREV | 162149 | 8.62 | 162,149 rows (5,310 distinct keys) have no matching previous_application.SK_ID_PREV |

### Columns with >= 50% nulls

| table | columns | examples |
|---|---|---|
| application_train | 41 | OWN_CAR_AGE, EXT_SOURCE_1, APARTMENTS_AVG, BASEMENTAREA_AVG, YEARS_BUILD_AVG, COMMONAREA_AVG |
| bureau | 2 | AMT_CREDIT_MAX_OVERDUE, AMT_ANNUITY |
| previous_application | 4 | AMT_DOWN_PAYMENT, RATE_DOWN_PAYMENT, RATE_INTEREST_PRIMARY, RATE_INTEREST_PRIVILEGED |

Full list in `findings.csv`.

## Column profiles

Per-column data type, nulls, distinct count, min, max and top 5 values are in `<table>_columns.csv`. Highest-null columns per table:

### application_train

| column | data_type | null_pct | distinct_count | min | max |
|---|---|---|---|---|---|
| COMMONAREA_AVG | double precision | 69.78 | 1968 | 0 | 1 |
| COMMONAREA_MODE | double precision | 69.78 | 1947 | 0 | 1 |
| COMMONAREA_MEDI | double precision | 69.78 | 1984 | 0 | 1 |
| NONLIVINGAPARTMENTS_MEDI | double precision | 69.26 | 120 | 0 | 1 |
| NONLIVINGAPARTMENTS_MODE | double precision | 69.26 | 96 | 0 | 1 |

### bureau

| column | data_type | null_pct | distinct_count | min | max |
|---|---|---|---|---|---|
| AMT_ANNUITY | double precision | 77.15 | 9045 | 0 | 24016036.5 |
| AMT_CREDIT_MAX_OVERDUE | double precision | 64.73 | 12752 | 0 | 9231525 |
| DAYS_ENDDATE_FACT | double precision | 37.24 | 2856 | -2916 | 0 |
| AMT_CREDIT_SUM_LIMIT | double precision | 33.32 | 7902 | -121905.675 | 2207250 |
| AMT_CREDIT_SUM_DEBT | double precision | 15.19 | 50900 | -1354875.615 | 59637690 |

### bureau_balance

| column | data_type | null_pct | distinct_count | min | max |
|---|---|---|---|---|---|
| SK_ID_BUREAU | bigint | 0.0 | 84828 | 5008808 | 6842877 |
| MONTHS_BALANCE | bigint | 0.0 | 97 | -96 | 0 |
| STATUS | text | 0.0 | 8 | 0 | X |

### previous_application

| column | data_type | null_pct | distinct_count | min | max |
|---|---|---|---|---|---|
| RATE_INTEREST_PRIVILEGED | double precision | 99.67 | 15 | 0.4244186046511628 | 0.8673361522198731 |
| RATE_INTEREST_PRIMARY | double precision | 99.67 | 55 | 0.05912104726283578 | 0.7009095545732745 |
| AMT_DOWN_PAYMENT | double precision | 52.76 | 9742 | 0 | 1404000 |
| RATE_DOWN_PAYMENT | double precision | 52.76 | 41057 | 0 | 0.9301973849763618 |
| NAME_TYPE_SUITE | text | 49.12 | 7 | Children | Unaccompanied |

### installments_payments

| column | data_type | null_pct | distinct_count | min | max |
|---|---|---|---|---|---|
| AMT_PAYMENT | double precision | 0.03 | 321937 | 0 | 3071320.785 |
| DAYS_ENTRY_PAYMENT | double precision | 0.03 | 3003 | -3078 | -2 |
| SK_ID_PREV | bigint | 0.0 | 138830 | 1000004 | 2843492 |
| SK_ID_CURR | bigint | 0.0 | 47414 | 100002 | 456247 |
| NUM_INSTALMENT_NUMBER | bigint | 0.0 | 241 | 1 | 242 |
