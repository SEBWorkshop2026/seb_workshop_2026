locals {
  participant_members = toset([
    for member in var.members : can(regex("^(user|group|serviceAccount):", member)) ? member : "user:${member}"
  ])
  dataform_participant_roles = setsubtract(toset([
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/dataform.editor",
  ]), toset([var.role]))
  dataform_participant_bindings = {
    for pair in setproduct(local.participant_members, local.dataform_participant_roles) :
    jsonencode(pair) => { member = pair[0], role = pair[1] }
  }
}

resource "google_project_service_identity" "dataform" {
  provider = google-beta
  project  = google_project_service.apis["dataform.googleapis.com"].project
  service  = "dataform.googleapis.com"
}

resource "google_service_account" "dataform" {
  project      = google_project.this.project_id
  account_id   = "dataform-workflows"
  display_name = "Dataform workflow execution"
}

resource "google_project_iam_member" "dataform_bigquery" {
  for_each = toset(["roles/bigquery.dataEditor", "roles/bigquery.jobUser"])

  project = google_project.this.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.dataform.email}"
}

resource "google_project_iam_member" "dataform_participants" {
  for_each = local.dataform_participant_bindings

  project = google_project.this.project_id
  role    = each.value.role
  member  = each.value.member
}

resource "google_service_account_iam_member" "dataform_participants" {
  for_each = local.participant_members

  service_account_id = google_service_account.dataform.name
  role               = "roles/iam.serviceAccountUser"
  member             = each.value
}

resource "google_service_account_iam_member" "dataform_agent" {
  for_each = toset(["roles/iam.serviceAccountUser", "roles/iam.serviceAccountTokenCreator"])

  service_account_id = google_service_account.dataform.name
  role               = each.value
  member             = "serviceAccount:${google_project_service_identity.dataform.email}"
}
