# Workshop projects

## Bootstrap the admin project and state bucket

Authenticate with `gcloud auth login` and `gcloud auth application-default login`.
Run the bootstrap script with an admin project ID, billing account ID, parent,
globally unique state bucket name, and bucket location:

```sh
./scripts/create_admin_project.sh \
  ws2026-admin BILLING_ACCOUNT_ID org:ORGANIZATION_ID ws2026-tfstate EU
```

For a folder, pass its numeric ID instead of `org:ORGANIZATION_ID`. Pass an
empty string (`""`) for no parent. The location cannot be changed after bucket
creation. The script reuses a bucket only when it belongs to the admin project
and is in the requested location. It enables object versioning, uniform
bucket-level access, and public access prevention. The bucket is bootstrapped
outside Terraform so it does not depend on the state it stores.

The account running the script needs permission to create or access the admin
project, link its billing account, enable APIs, and create and configure the
bucket. Terraform's application default credentials also need access to the
bucket (for example, Storage Object Admin). State may contain sensitive data;
restrict bucket access accordingly.

## Migrate or initialize state

Set `admin_project_id` and the other inputs in `terraform.tfvars`, then run:

```sh
terraform init -migrate-state -backend-config="bucket=ws2026-tfstate"
```

Use the bucket name passed to the bootstrap script. When migrating existing
local state, review and accept Terraform's migration prompt. Confirm the
result with `terraform state list`. Terraform may leave a local backup; secure
it because it can contain sensitive data. On a fresh checkout, use the same
`terraform init` command and bucket name to connect to the existing state.
The GCS backend supports state locking, but all operators must use the same
bucket and backend prefix.

GCP budgets send alerts; they do not stop spending.

## Organization administrators

To grant the six organization-level administrator roles to individual Google
accounts, set the numeric organization ID and bare user email addresses in
`terraform.tfvars`:

```hcl
org_id = "123456789012"
admin_users = [
  "admin1@example.com",
  "admin2@example.com",
]
```

`admin_users` defaults to empty. Set `org_id` even if `folder_id` is set;
projects will still be created in the folder. Apply the configuration using an
account that can manage the organization's IAM policy. Terraform grants each
user IAM Workforce Pool Admin, Owner, Organization Administrator, Project
Creator, Project Mover, and Service Usage Admin. Owner is a broad role inherited
by descendant resources, including projects; these grants affect the whole
organization, not just workshop projects. Removing a user from the list or
destroying this configuration removes the grants managed by Terraform.
Review the plan before applying, especially if a role is already granted
outside Terraform: import existing grants rather than managing the same grant
in multiple places.

These roles do not automatically grant access to billing accounts or to
resources outside the organization. Provision any additional storage and
billing permissions separately. Organization Administrator and Owner provide
broad administrative access, including the ability to change IAM. The bootstrap
admin project must be under the organization for organization-level permissions
to apply to it.

## Sync Terraform variables

After signing in with `gcloud auth login`, use the existing state bucket to
transfer all root-level `*.tfvars` and `*.tfvars.json` files between laptops:

```sh
./scripts/tfvars.sh upload
./scripts/tfvars.sh download
```

Both commands default to the `ws2026-tfstate` bucket; pass a different bucket
name as the second argument if needed. Download overwrites matching local
files; upload replaces matching remote files but does not delete files that
no longer exist locally. Downloads and uploads can partially complete if a transfer
fails. Download requires permission to list objects in the bucket. Sync is
manual, so download before editing and upload after changes.
Check that your variable files are ignored by Git. Anyone with sufficient
bucket access can read both the variables and the Terraform state; restrict
that access accordingly.

## Assign Classroom students to projects

Put a Google OAuth access token in the local `credential.json` file:

```json
{"access_token": "YOUR_ACCESS_TOKEN"}
```

Authorize as a teacher of the active class with these scopes:

```text
https://www.googleapis.com/auth/classroom.courses.readonly
https://www.googleapis.com/auth/classroom.rosters.readonly
https://www.googleapis.com/auth/classroom.profile.emails
```

You can obtain a token with [Google's OAuth Playground](https://developers.google.com/oauthplayground/).
The token expires and cannot be refreshed by this script; replace it when
needed. Access to the Classroom API and roster must be allowed for the
authorized account. `credential.json` is ignored by Git and should be kept
private. Use `--credentials` to select a different JSON file.

Run the script with `uv` from the repository root. `uv` installs its declared
dependencies automatically:

```sh
uv run scripts/assign_classroom_projects.py \
  --class-name "YOUR CLASS NAME"
terraform plan
terraform apply
```

The script sorts emails and assigns one student to each project starting at 1.
It fails if the roster is empty, emails are missing or duplicated, or multiple
active classes have that name. Each successful run replaces
`classroom-assignments.auto.tfvars.json`; use `--output` to select a different
file. Set Terraform's `project_count` to at least the number of students;
Terraform rejects assignments beyond that count.

The JSON variable file replaces the entire `assignments` map from
`terraform.tfvars`, not just individual entries. Review the generated file
and Terraform plan before applying: adding or removing students can change
project assignments and revoke access. Terraform automatically loads the
default file from the repository root; custom outputs outside that directory
or without the `.auto.tfvars.json` suffix must be supplied with `-var-file`.
Other variable files or command-line arguments can override the assignments.
The generated default file is ignored by Git; protect it, any custom output
paths, and your credentials, and transfer the assignment file securely between
operators.

## BigQuery and Dataform

BigQuery and Dataform APIs are enabled in every project, including the shared
project, even when `enabled_apis` is customized. Each participant project has
its own `dataform-workflows` service account with BigQuery data editor and job
user roles. Assigned participants get BigQuery data editor and job user,
Dataform editor, and permission to use their project's execution account. The
Dataform service agent can impersonate that account for workflow execution.

When creating a Dataform repository, select the project's
`dataform-workflows` service account. Run `terraform output
dataform_service_accounts` to see the account for each project. Assign
participants through `assignments` and re-apply Terraform to grant them access.
The shared project grants BigQuery data viewer to assigned participants, extra
shared viewers, and each project's Dataform execution account, allowing queries
and workflows to read shared datasets. Jobs should run in the participant's
project; access to shared data does not grant shared-project job creation.
Dataset-level restrictions, organization policies, or location mismatches can
still prevent access or queries.

These roles allow participants to create BigQuery jobs and modify data in their
own projects, and to run Dataform workflows using the execution account.
BigQuery usage can incur charges, and budgets do not enforce a spending limit.

Each participant project also gets a custom-mode VPC named `default` with one
subnet (`10.0.0.0/24`, Private Google Access on) in `notebook_region`
(default `europe-central2`). BigQuery Studio Python notebooks run on Colab
Enterprise, whose default runtime uses this network. 
A `Workshop` runtime template in the same region pins the network and subnetwork.

The [Dataform project](dataform/README.md) loads one chosen reporting date from
the shared BigQuery and CSV sources into bronze tables, cleans and casts them
into silver tables, then builds a gold star schema and loan snapshot in a
participant project. Terraform creates the `external`, `bronze`, `silver` and
`gold` datasets (EU) in every workshop project, and the PDF extraction session
adds a `credit_memos` dataset.

## Load synthetic banking data

After applying Terraform, authenticate application default credentials with
`gcloud auth application-default login`. Terraform creates a private EU bucket
named `<shared-project-id>-csv` for the CSV source data. Its name must be
globally available; set `shared_csv_bucket_name` to a different globally unique
name if it is already taken. Storage API is enabled in the shared project even
when omitted from `enabled_apis`. Assigned participants, extra shared viewers,
and workshop Dataform service accounts have object viewer access. The Terraform
operator needs permission to create the bucket and manage its IAM policy. An
administrator loading data needs BigQuery dataset creation, table creation/update
and job creation permissions, as well as permission to read the bucket metadata
and create or replace its objects.

```sh
uv run --project sample_data sample-data \
  --project "$(terraform output -raw shared_project)" \
  --bucket "$(terraform output -raw shared_csv_bucket)"
```

The generator replaces three monthly-partitioned BigQuery tables and writes
monthly CSV files for three source systems to the bucket. It uses 10,000 synthetic Lithuanian
mortgages and a fixed seed by default. See [sample_data/README.md](sample_data/README.md)
for the source schemas, dates, risk assumptions, and limitations.

Each run replaces those three tables and the 75 CSV objects under the selected
prefix; unrelated tables and objects, including legacy tables from earlier
versions of the generator, are not removed. A failed run may leave mixed
generations; rerun it to complete the load. BigQuery and Cloud Storage may
incur charges.

The bucket has uniform bucket-level access and public access prevention
enabled. Terraform will not destroy it while it contains objects; remove or
relocate the objects deliberately before destroying or renaming the bucket.
Object access grants do not include permission to upload or replace CSVs.
