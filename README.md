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

## Virtual participant setup

Workshop project 02 hosts 50 virtual participant slots by default; set
`participant_count` to change this. Each slot has a Dataform repository named
`participant-N` and EU datasets `external_N`, `bronze_N`, `silver_N`, `gold_N`
and `credit_memos_N`. Workspace compilation overrides direct outputs to those
datasets. Repositories are created empty; create a workspace in each repository
and upload the [Dataform project](dataform/README.md#setup) before use.

Assignments map each slot to at most one Google user. Assigned users get
BigQuery job permission in project 02, data editor on their own datasets, and
Dataform editor on their own repository, not project-wide Dataform repository
creation or BigQuery data access. Participants can read the shared input data
and use the shared credit memo connection. They must choose **Execute with user
credentials** and authorize their Google Account when running Dataform. No
custom Dataform execution accounts are configured by this repository.

Dataset and repository IAM cannot override broader permissions inherited from
the organization, project, groups, or grants outside this configuration. Audit
those grants before relying on isolation. Dataform repository names may be
listed by other participants. The credit memo connection uses its own
Google-managed service account to access the PDFs and Gemini.

Project 02 is moved in Terraform state rather than recreated. Review the plan
before applying: existing participant project-wide grants and the custom
Dataform execution accounts in all workshop projects are removed. Existing
Dataform workflows using those accounts must be migrated to user credentials.
Terraform-managed
participant access to workshop projects 01 and 03 is also removed. Audit
inherited or externally managed permissions separately.
Existing unsuffixed datasets are retained. Reducing `participant_count` can
delete datasets and their contents; repositories with workspaces may require
manual cleanup.

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

Run the script with `uv` from the repository root. `uv` installs its declared
dependencies automatically:

```sh
uv run scripts/assign_classroom_projects.py \
  --class-name "YOUR CLASS NAME"
terraform plan
terraform apply
```

If `credential.json` does not exist, the script opens Google's OAuth Playground
with the Classroom scopes selected. Click **Authorize APIs**, sign in as a
teacher of the active class, and grant access. Click **Exchange authorization
code for tokens**, copy the **Access token** (not the refresh token), and paste
it into the terminal prompt. The input is hidden. The script saves the token in
`credential.json`, restricts the file to the current user, and continues with
the assignment. If the browser does not open, use the printed link. No custom
OAuth client is required.

The script reuses an existing `credential.json`. Alternatively, create it
yourself:

```json
{"access_token": "YOUR_ACCESS_TOKEN"}
```

Authorize as a teacher of the active class with these scopes:

```text
https://www.googleapis.com/auth/classroom.courses.readonly
https://www.googleapis.com/auth/classroom.rosters.readonly
https://www.googleapis.com/auth/classroom.profile.emails
```

When Classroom rejects the saved token as expired or invalid, the script opens
the Playground and asks for a replacement, then retries once. This requires an
interactive terminal and your sign-in and consent; the token is not refreshed
automatically. You can also replace it explicitly:

```sh
uv run scripts/assign_classroom_projects.py \
  --class-name "YOUR CLASS NAME" --authorize
```

Access to the Classroom API and roster must be allowed for the authorized
account. Playground's OAuth client may be subject to Google's restrictions or
unverified-app warnings. `credential.json` is ignored by Git and should be kept
private. Use `--credentials` to select a different JSON file; custom paths may
not be ignored by Git.

The script assigns each student a virtual slot in project 02. It preserves
existing slots when the roster changes, reserves departed students' slots as
empty, and assigns new students unused higher-numbered slots. It fails if the
roster is empty, emails are missing or duplicated, or multiple active classes
have that name. Each successful run replaces
`classroom-assignments.auto.tfvars.json`; use `--output` to select a different
file. If `participant_count` differs from 50, pass the same value to
`--participant-count`. The script reads the existing output to preserve slot
ownership; do not delete or replace it when syncing a roster. If all slots
have been used, increase the count. Reassigning an old slot manually can expose
the previous participant's data; remove or secure that data first.

The JSON variable file replaces the entire `assignments` map from
`terraform.tfvars`, not just individual entries. Review the generated file
and Terraform plan before applying: adding or removing students can change
participant assignments and revoke access. Terraform automatically loads the
default file from the repository root; custom outputs outside that directory
or without the `.auto.tfvars.json` suffix must be supplied with `-var-file`.
Other variable files or command-line arguments can override the assignments.
The generated default file is ignored by Git; protect it, any custom output
paths, and your credentials, and transfer the assignment file securely between
operators.

## BigQuery and Dataform

BigQuery and Dataform APIs are enabled in every project, including the shared
project, even when `enabled_apis` is customized. Project 02 uses the virtual
participant setup above. The shared project grants BigQuery data viewer to
assigned participants and extra shared viewers. Jobs should run in the
participant project. Dataset-level restrictions, organization policies, or
location mismatches can still prevent access or queries.

BigQuery usage can incur charges, and budgets do not enforce a spending limit.

Each participant project also gets a custom-mode VPC named `default` with one
subnet (`10.0.0.0/24`, Private Google Access on) in `notebook_region`
(default `europe-central2`). BigQuery Studio Python notebooks run on Colab
Enterprise, whose default runtime uses this network. 
A `Workshop` runtime template in the same region pins the network and subnetwork.

The [Dataform project](dataform/README.md) loads one chosen reporting date from
the shared BigQuery and CSV sources into bronze tables, cleans and casts them
into silver tables, then builds a gold star schema and loan snapshot in a
participant project. The virtual participant setup creates suffixed datasets
in project 02; the original unsuffixed datasets remain in the workshop projects.

## Load synthetic banking data

After applying Terraform, authenticate application default credentials with
`gcloud auth application-default login`. Terraform creates a private EU bucket
named `<shared-project-id>-csv` for the CSV source data. Its name must be
globally available; set `shared_csv_bucket_name` to a different globally unique
name if it is already taken. Storage API is enabled in the shared project even
when omitted from `enabled_apis`. Assigned participants and extra shared viewers
have object viewer access. The Terraform
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
