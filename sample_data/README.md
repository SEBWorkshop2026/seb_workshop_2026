# Synthetic mortgage source systems

The generator produces illustrative data, not real borrower records or a
calibrated credit-risk model. Run it from the repository root:

```sh
uv run --project sample_data sample-data \
  --project YOUR_PROJECT_ID --bucket YOUR_EXISTING_BUCKET
```

The bucket must exist and be readable and writable by the application default
credentials. The BigQuery dataset is created if needed. The defaults are:
- `--dataset banking_sample`
- `--location EU`
- `--prefix banking_sample`
- `--count 10000`
- `--seed 2026`

## Sources and joins

| System | Destination | Grain and key |
| --- | --- | --- |
| Debtor Info | BigQuery `debtor_info` | One row per debtor and snapshot, `debtor_identifier` |
| Debtor Financial | GCS `banking_sample/debtor_financial/YYYY-MM-DD.csv` | One row per debtor and snapshot |
| Arrangement Balance | GCS `banking_sample/arrangement_balance/YYYY-MM-DD.csv` | One row per loan and snapshot |
| Arrangement Account Info | BigQuery `arrangement_account_info` | One row per loan and snapshot, `loan_id` |
| Collateral | GCS `banking_sample/collateral/YYYY-MM-DD.csv` | One property per loan and snapshot, `loan_id` |
| Defaults | BigQuery `defaults` | One row per defaulted loan and snapshot, `loan_id` |

Use the account's `debtor_id` to join to the debtor systems'
`debtor_identifier`; use `loan_id` to join the remaining systems. Join all
systems on `reporting_date` as well. Each BigQuery table is monthly-partitioned
on this date. Defaults are cumulative snapshots: a loan appears in every
snapshot on or after its `default_date`, so use a single snapshot or
deduplicate by `loan_id` and `default_date` when analyzing events.
Co-debtor IDs reference another generated
debtor; an absent co-debtor is null. The CSVs have headers and empty fields
represent nulls. Debtor Financial, Arrangement Balance, Arrangement Account
Info and Collateral each include a `currency` field, set to `EUR` for every
row and applying to all monetary amounts in that row. Income, household
income, funds available, and next payment are monthly amounts. Interest rates
are annual percentages.
Account dates are integers in `YYYYMMDD` format; other dates are ISO dates.
LTV is current principal divided by property value, expressed as a ratio
(1.0 means 100%).

All systems have monthly snapshots from 2024-01-01 through 2026-01-01
inclusive. All loans are performing at the initial snapshot. BigQuery debtor
and account attributes remain constant between snapshots, while the defaults
table records defaults known at each snapshot.
Principal follows a simplified annuity schedule until arrears; LTV changes with
the balance. Defaults occur after the initial snapshot and before the last
snapshot. `loan_status` reflects whether a default has happened by the
snapshot date. `inv_due_date` tracks the oldest missed payment in the
simulated arrears episode: default occurs on day 91 and some other borrowers
cure their arrears. After a cure, the schedule resumes as if missed principal
was repaid. Defaulted loans do not cure.

Property values, rates, income and other financial attributes remain fixed
throughout the snapshots. This includes variable rates: no historical Euribor
series, interest resets, property-price changes, refinance, or new
originations during the observation window are simulated. The cohort was
originated in 2020-2023 and is not a representative cross-section of all
outstanding mortgages. Co-borrowers have their own debtor and financial rows;
both members of a generated household share its region, number of children,
total income and available funds. Their ages are generated close to each
other. `funds_available` is a simplified household amount after the simulated
mortgage payment and assumed living expenses, not a measured statistic.