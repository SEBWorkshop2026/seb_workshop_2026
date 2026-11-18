# Bronze and silver Dataform pipeline

This project reads the three shared BigQuery source tables and the three CSV
sources into six native BigQuery tables in a participant project's `bronze`
dataset. CSV external tables are created in the participant project's
`external` dataset. The silver models are created in the participant project's
`silver` dataset. All three datasets are in `EU`; bronze tables are partitioned
monthly by `reporting_date`.

## Silver models

Silver models retain a snapshot for each loaded reporting period. Each run
replaces only the selected period, including when periods are loaded out of
order. Load each desired reporting period separately.

| Model | Grain and behavior |
| --- | --- |
| `dim_debtor` | One row per debtor and reporting date, joining debtor info and financial snapshots by debtor and date. Missing financial data remains null. |
| `dim_loan` | One row per loan and reporting date; origination and maturity are converted to `DATE`. |
| `bridge_loan_debtor` | Primary and non-null co-debtor relationships per loan and reporting date, with roles `primary` and `co`. |
| `fct_loan_balance` | One row per loan and reporting date, including balances, payment, annual percentage rate, status, and invoice due date. |
| `fct_collateral` | One row per collateral, loan, and reporting date, including property value and the source LTV ratio. |
| `fct_default` | One row per loan, default date, and reporting date, incrementally replacing the selected cumulative snapshot. |

Join dimensions, the bridge, and facts on `reporting_date` as well as their
entity keys to use matching snapshots. The models assume the source grains
described in the [sample data documentation](../sample_data/README.md); repeated
source keys can produce duplicate silver rows within a period. Currency remains
a column on monetary models, not a separate dimension. All silver tables are
monthly-partitioned by reporting date. Date attributes can be derived directly
from the date columns in BigQuery.
The default fact deduplicates within each reporting snapshot. Since snapshots
are cumulative, a default appears in multiple periods: filter on
`reporting_date` or deduplicate by loan and default date when counting events.
Rerunning a period replaces that snapshot without changing other periods.

## Setup

1. Apply the workshop Terraform configuration, including the bucket permissions.
   Load the sample data into `ws2026-shared.banking_sample` and the shared CSV
   bucket using the generator.
2. Create a Dataform repository and workspace in the participant project. To
   upload this directory to the workspace linked in the workshop, run from
   the workshop repository:

   ```sh
   gcloud auth login
   python3 scripts/upload_dataform.py
   ```

   The defaults are project `ws2026-01`, location `europe-west1`, repository
   `first_repo`, and workspace `dev_workspace_1`. Override these with
   `--project`, `--location`, `--repository`, or `--workspace`. The script
   uses `gcloud` credentials to call the Dataform API, because `gcloud` has no
   Dataform workspace file command. It refuses to overwrite differing files
   unless `--overwrite` is supplied. Review workspace changes before using it:

   ```sh
   python3 scripts/upload_dataform.py --overwrite
   ```

   Hidden files and `node_modules` are not uploaded. Other workspace files are
   not deleted; the script lists extra SQLX and JavaScript files under
   `definitions` and `includes` because they may affect compilation. Uploads
   are not atomic; rerun after fixing an error. The script writes uncommitted
   workspace files, not a Git commit or push. Commit and push separately in
   Dataform if needed. Dataform requires `workflow_settings.yaml` at the
   repository root; connecting this workshop repository unchanged leaves the
   file in a subdirectory.
3. Configure the repository to run using that project's `dataform-workflows`
   service account. The account needs permission to create datasets and tables
   in the participant project, run BigQuery jobs, read the shared tables, and
   read the CSV bucket and its metadata. The workshop Terraform grants these
   permissions, subject to dataset restrictions and organization policies.
4. `workflow_settings.yaml` defaults to `ws2026-01`. Set `defaultProject` to
   your participant project or override `defaultDatabase` at compilation. Set
   `csv_bucket` to the actual `terraform output -raw shared_csv_bucket` value
   if it differs from `ws2026-shared-csv`.

## Run a reporting period

Set `reporting_period` as a compilation variable in `YYYY-MM` format. It
defaults to `2025-03`, so a workspace run without an override will process that
month. The pipeline uses the first day of the month to select both the shared
BigQuery rows and the CSV filename, for example
`banking_sample/debtor_financial/2025-03-01.csv`.

For a programmatic run, call the
[Dataform compilationResults.create API](https://cloud.google.com/dataform/reference/rest/v1/projects.locations.repositories.compilationResults/create)
with a Git commit or workspace and the overrides. For example, with a Git
remote configured:

```json
{
  "gitCommitish": "main",
  "codeCompilationConfig": {
    "defaultDatabase": "YOUR_PARTICIPANT_PROJECT",
    "vars": {
      "reporting_period": "2025-03",
      "csv_bucket": "ws2026-shared-csv"
    }
  }
}
```

Check `compilationErrors` in the response. Then call
[workflowInvocations.create](https://cloud.google.com/dataform/reference/rest/v1/projects.locations.repositories.workflowInvocations/create)
in the same repository with the returned compilation result's full `name`:

```json
{
  "compilationResult": "projects/PROJECT/locations/LOCATION/repositories/REPOSITORY/compilationResults/RESULT"
}
```

The repository's configured execution account runs the invocation. Check the
invocation's final state for success. For a different period, create a new
compilation result with the new period and invoke it. A console release
configuration can also set compilation variables.

## Create historical releases

Once the Dataform repository's remote `main` branch contains this project at
its root, create a release for each sample snapshot (2024-01 through 2026-01,
inclusive):

```sh
gcloud auth login
python3 scripts/create_historical_releases.py \
  --project YOUR_PARTICIPANT_PROJECT --csv-bucket YOUR_SHARED_CSV_BUCKET
```

Run this from the workshop repository. Defaults match the workspace upload
script: project `ws2026-01`, location `europe-west1`, and repository
`first_repo`; override them with `--project`, `--location`, and `--repository`.
The default bucket is `ws2026-shared-csv`. The caller needs permission to
create, read and update Dataform release configurations and create compilation
results. The repository must be connected to a remote containing `main` and
the desired changes must be committed and pushed there; workspace edits are
not used.

The script creates 25 unscheduled `historical-YYYY-MM` release configurations,
compiles each from `main` with that reporting period and publishes its live
compilation result. It does **not** run the releases or load data.
Existing matching releases with live compilations are left unchanged; matching
releases without one are compiled, so rerunning can resume after a failure.
A conflicting configuration stops the script without modifying it. Earlier
releases may already have been created when an error occurs. A subsequent run
does not refresh existing live compilations after `main` changes; update them
deliberately in Dataform if needed.

## Run historical releases

After creating the releases and loading the sample sources, run:

```sh
python3 scripts/run_historical_releases.py --project YOUR_PARTICIPANT_PROJECT
```

The script uses the same default project, location, and repository as the release
creator; override them with `--project`, `--location`, and `--repository`. It
checks each release's reporting-period setting and live compilation result
reference, then executes all 25 periods chronologically, waiting for each
invocation to succeed before starting the next. It uses the repository's
configured execution account and does not request a full refresh. Ensure the
live compilations correspond to their release settings; changing a release
config does not automatically recompile it. The caller needs permission to read release configurations and
create and read workflow invocations, and to use the execution service account.

The runner stops on an error, failure, cancellation, or unexpected state.
After investigating and ensuring no invocation is still running, use
`--start-period YYYY-MM` to resume from the affected period. The script does not
cancel a running invocation if interrupted, and a network error during invocation
creation can leave an invocation running even if its name was not returned.
Check Dataform before retrying. Do not run this script concurrently with any
other invocation against the same tables. Executions can incur BigQuery charges.

## Reruns and limitations

Each bronze and silver incremental model creates its table on the first run. On
later runs, its pre-operation deletes the selected reporting date, then Dataform
inserts the rows for that date. Bronze rows have an `_ingested_at`
timestamp; bronze CSV rows also have a `_source_file`. The external tables use
the existing CSV paths, not Hive partitions.

The delete and insert are separate operations, not a transaction. If a source
is missing or empty, or insertion fails after the delete, existing rows for the
selected period can be lost. Other models may already have completed; fix the
issue and rerun the period. Run one invocation at a time.

A Dataform full refresh recreates each bronze and silver table using only the
selected period and removes other periods. If bronze tables were created by the
earlier custom-operation pipeline, add nullable `_ingested_at` TIMESTAMP
columns to all six tables and nullable `_source_file` STRING columns to the
three CSV tables before running these models. A full refresh also changes the
schema, but discards other periods.
The generator overwrites CSVs, so this pipeline retains the latest loaded
version of each reporting date, not an immutable history of deliveries.
If `silver.dim_debtor`, `silver.dim_loan`, or `silver.bridge_loan_debtor`
already exists from the earlier unpartitioned models, back up any data you
need, then drop those tables before running the new models. The same applies to
`silver.fct_default` if it exists from the earlier event-grain model partitioned
by default date. BigQuery cannot replace a table with a different partitioning
specification. Rerun each desired reporting period to populate snapshots.

The date dimension is no longer defined. Uploading does not delete old
workspace files, so remove an existing `definitions/silver/dim_date.sqlx`
from the Dataform workspace separately. Removing its definition does not delete
an existing BigQuery table.
