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
