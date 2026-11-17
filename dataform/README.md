# Bronze Dataform pipeline

This project reads the three shared BigQuery source tables and the three CSV
sources into six native BigQuery tables in a participant project's `bronze`
dataset. CSV external tables are created in the participant project's
`external` dataset. Both datasets are in `EU`; bronze tables are partitioned
monthly by `reporting_date`.

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

## Reruns and limitations

Each incremental model creates its table on the first run. On later runs, its
pre-operation deletes the selected reporting date, then Dataform inserts the
rows for that date. Each row has an `_ingested_at` timestamp; CSV rows also
have a `_source_file`. The external tables use the existing CSV paths, not Hive
partitions.

The delete and insert are separate operations, not a transaction. If a source
is missing or empty, or insertion fails after the delete, existing rows for the
selected period can be lost. Other models may already have completed; fix the
issue and rerun the period. Run one invocation at a time.

A Dataform full refresh recreates each table using only the selected period and
removes other periods. If tables were created by the earlier custom-operation
pipeline, add nullable `_ingested_at` TIMESTAMP columns to all six tables and
nullable `_source_file` STRING columns to the three CSV tables before running
these models. A full refresh also changes the schema, but discards other periods.
The generator overwrites CSVs, so this pipeline retains the latest loaded
version of each reporting date, not an immutable history of deliveries.
