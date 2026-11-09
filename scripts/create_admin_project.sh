#!/usr/bin/env bash
# Creates the admin project and its Terraform state bucket.
# Usage: ./scripts/create_admin_project.sh <project_id> <billing_account_id> <folder_id|org:<org_id>|""> <bucket_name> <bucket_location>
set -euo pipefail

PROJECT_ID="${1:?project ID required}"
BILLING_ACCOUNT="${2:?billing account ID required}"
PARENT="${3:-}"
STATE_BUCKET="${4:?state bucket name required}"
STATE_LOCATION="${5:?state bucket location required}"

args=()
if [[ -n "$PARENT" ]]; then
  if [[ "$PARENT" == org:* ]]; then
    args+=(--organization="${PARENT#org:}")
  else
    args+=(--folder="$PARENT")
  fi
fi

if gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
  echo "Project $PROJECT_ID already exists, reusing it."
else
  gcloud projects create "$PROJECT_ID" --name="Workshop Admin" "${args[@]}"
fi

billing_enabled="$(gcloud billing projects describe "$PROJECT_ID" --format='value(billingEnabled)')"
if [[ "$billing_enabled" == "True" ]]; then
  current_billing_account="$(gcloud billing projects describe "$PROJECT_ID" --format='value(billingAccountName)')"
  if [[ "$current_billing_account" != "billingAccounts/$BILLING_ACCOUNT" ]]; then
    echo "Project $PROJECT_ID is already linked to $current_billing_account, not billingAccounts/$BILLING_ACCOUNT." >&2
    exit 1
  fi
  echo "Project $PROJECT_ID is already linked to billing account $BILLING_ACCOUNT."
else
  gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT"
fi

gcloud services enable \
  cloudbilling.googleapis.com \
  billingbudgets.googleapis.com \
  cloudresourcemanager.googleapis.com \
  serviceusage.googleapis.com \
  iam.googleapis.com \
  storage.googleapis.com \
  --project "$PROJECT_ID"

bucket_names="$(gcloud storage buckets list --project="$PROJECT_ID" --format='value(name)')"
if grep -Fxq -- "$STATE_BUCKET" <<< "$bucket_names"; then
  bucket_location="$(gcloud storage buckets describe "gs://$STATE_BUCKET" --format='value(location)')"
  if [[ "${bucket_location^^}" != "${STATE_LOCATION^^}" ]]; then
    echo "Bucket $STATE_BUCKET already exists in $bucket_location, not $STATE_LOCATION." >&2
    exit 1
  fi
  echo "Bucket $STATE_BUCKET already exists in $PROJECT_ID, reusing it."
else
  gcloud storage buckets create "gs://$STATE_BUCKET" \
    --project="$PROJECT_ID" \
    --location="$STATE_LOCATION" \
    --uniform-bucket-level-access \
    --public-access-prevention
fi

gcloud storage buckets update "gs://$STATE_BUCKET" \
  --versioning \
  --uniform-bucket-level-access \
  --public-access-prevention

gcloud auth application-default set-quota-project "$PROJECT_ID"

echo "Done. Set admin_project_id = \"$PROJECT_ID\" in terraform.tfvars."
echo "Initialize the backend with: terraform init -migrate-state -backend-config=\"bucket=$STATE_BUCKET\""
