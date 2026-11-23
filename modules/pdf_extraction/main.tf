# PDF AI extraction session: credit memo archive and per-participant Gemini access.
#
# Shared project: one private EU bucket with the credit memo PDFs and the label file.
# Each participant project: BigQuery Connection and Agent Platform (Vertex AI) APIs, a credit memo
# dataset, a Cloud resource connection in EU whose service account reads the bucket and calls Gemini,
# and permission for the participants and the project's Dataform execution account to use that
# connection.

terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
    }
  }
}

locals {
  bucket_name = var.bucket_name != null ? var.bucket_name : "${var.shared_project_id}-credit-memos"

  participant_members = {
    for number, p in var.participant_projects : number => toset([
      for m in p.members : can(regex("^(user|group|serviceAccount):", m)) ? m : "user:${m}"
    ])
  }

  # every assigned participant, their Dataform account and extra viewers can browse the archive.
  # Static keys: Dataform account emails are unknown until the accounts exist (first apply).
  bucket_viewers = merge(
    { for m in toset(concat(
      flatten([for number, members in local.participant_members : tolist(members)]),
      [for m in var.extra_viewers : can(regex("^(user|group|serviceAccount):", m)) ? m : "user:${m}"],
    )) : "viewer:${m}" => m },
    { for number, p in var.participant_projects : "dataform:${number}" => "serviceAccount:${p.dataform_service_account}" },
  )

  project_apis = {
    for pair in setproduct(keys(var.participant_projects), ["bigqueryconnection.googleapis.com", "aiplatform.googleapis.com"]) :
    "${pair[0]}/${pair[1]}" => { number = pair[0], service = pair[1] }
  }

  connection_users = merge([
    for number, p in var.participant_projects : merge(
      { for m in local.participant_members[number] : "${number}/${m}" => { number = number, member = m } },
      { "${number}/dataform" = { number = number, member = "serviceAccount:${p.dataform_service_account}" } },
    )
  ]...)

  memo_files = var.memo_source_dir == null ? toset([]) : fileset("${var.memo_source_dir}/pdf", "*.pdf")
}

# ---------------------------------------------------------------- shared archive
resource "google_storage_bucket" "memos" {
  project                     = var.shared_project_id
  name                        = local.bucket_name
  location                    = var.location
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

resource "google_storage_bucket_object" "pdf" {
  for_each = local.memo_files

  bucket       = google_storage_bucket.memos.name
  name         = "pdf/${each.value}"
  source       = "${var.memo_source_dir}/pdf/${each.value}"
  content_type = "application/pdf"
}

resource "google_storage_bucket_object" "labels" {
  count = var.memo_source_dir == null ? 0 : 1

  bucket       = google_storage_bucket.memos.name
  name         = "ground_truth.csv"
  source       = "${var.memo_source_dir}/ground_truth.csv"
  content_type = "text/csv"
}

resource "google_storage_bucket_iam_member" "viewers" {
  for_each = local.bucket_viewers

  bucket = google_storage_bucket.memos.name
  role   = "roles/storage.objectViewer"
  member = each.value
}

# ---------------------------------------------------------------- per participant project
resource "google_project_service" "apis" {
  for_each = local.project_apis

  project            = var.participant_projects[each.value.number].project_id
  service            = each.value.service
  disable_on_destroy = false
}

resource "google_bigquery_connection" "gemini" {
  for_each = var.participant_projects

  project       = each.value.project_id
  connection_id = var.connection_id
  location      = var.location
  friendly_name = "Credit memo extraction"
  description   = "Reads the credit memo PDFs and calls Gemini for AI.GENERATE_TABLE."

  cloud_resource {}

  depends_on = [google_project_service.apis]
}

# dataset for the object table over the PDFs and the extraction results
resource "google_bigquery_dataset" "memos" {
  for_each = var.participant_projects

  project                    = each.value.project_id
  dataset_id                 = var.dataset_id
  location                   = var.location
  description                = "Credit memo object table and Gemini extraction results."
  delete_contents_on_destroy = true
}

# the connection's service account reads the PDFs ...
resource "google_storage_bucket_iam_member" "connection_reader" {
  for_each = google_bigquery_connection.gemini

  bucket = google_storage_bucket.memos.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${each.value.cloud_resource[0].service_account_id}"
}

# ... and calls Gemini on Agent Platform (formerly Vertex AI) in its own project
resource "google_project_iam_member" "connection_aiplatform" {
  for_each = google_bigquery_connection.gemini

  project = each.value.project
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${each.value.cloud_resource[0].service_account_id}"
}

# participants and the project's Dataform execution account may use the connection
resource "google_bigquery_connection_iam_member" "users" {
  for_each = local.connection_users

  project       = google_bigquery_connection.gemini[each.value.number].project
  location      = google_bigquery_connection.gemini[each.value.number].location
  connection_id = google_bigquery_connection.gemini[each.value.number].connection_id
  role          = "roles/bigquery.connectionUser"
  member        = each.value.member
}
