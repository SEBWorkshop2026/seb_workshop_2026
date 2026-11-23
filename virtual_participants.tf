locals {
  participant_slots = { for n in range(1, var.participant_count + 1) : tostring(n) => n }
  participant_users = {
    for slot, members in var.assignments : slot => (
      startswith(members[0], "user:") ? members[0] : "user:${members[0]}"
    ) if length(members) == 1
  }
  participant_datasets = {
    for pair in setproduct(keys(local.participant_slots), ["external", "bronze", "silver", "gold", "credit_memos"]) :
    "${pair[0]}/${pair[1]}" => { slot = pair[0], dataset = "${pair[1]}_${pair[0]}" }
  }
}

resource "google_bigquery_dataset" "participant" {
  for_each = local.participant_datasets

  project                    = module.participant_project.project_id
  dataset_id                 = each.value.dataset
  location                   = "EU"
  delete_contents_on_destroy = true

  depends_on = [module.participant_project]
}

resource "google_bigquery_dataset_iam_member" "participant" {
  for_each = {
    for key, dataset in local.participant_datasets : key => dataset
    if contains(keys(local.participant_users), dataset.slot)
  }

  project    = module.participant_project.project_id
  dataset_id = google_bigquery_dataset.participant[each.key].dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = local.participant_users[each.value.slot]
}

resource "google_dataform_repository" "participant" {
  provider = google-beta
  for_each = local.participant_slots

  project = module.participant_project.project_id
  region  = var.dataform_region
  name    = "participant-${each.key}"

  workspace_compilation_overrides {
    default_database = module.participant_project.project_id
    schema_suffix    = each.key
  }

  depends_on = [module.participant_project]
}

resource "google_dataform_repository_iam_member" "participant" {
  provider = google-beta
  for_each = local.participant_users

  project    = module.participant_project.project_id
  region     = var.dataform_region
  repository = google_dataform_repository.participant[each.key].name
  role       = "roles/dataform.editor"
  member     = each.value
}

resource "google_project_iam_custom_role" "participant_dataform_discovery" {
  project     = module.participant_project.project_id
  role_id     = "workshopDataformDiscovery"
  title       = "Workshop Dataform discovery"
  permissions = ["dataform.locations.get", "dataform.locations.list", "dataform.repositories.list", "resourcemanager.projects.get"]
}

resource "google_project_iam_member" "participant_dataform_discovery" {
  for_each = local.participant_users

  project = module.participant_project.project_id
  role    = google_project_iam_custom_role.participant_dataform_discovery.name
  member  = each.value
}

resource "google_project_iam_member" "participant_bigquery_jobs" {
  for_each = local.participant_users

  project = module.participant_project.project_id
  role    = "roles/bigquery.jobUser"
  member  = each.value
}

resource "google_storage_bucket_iam_member" "participant_csv_metadata" {
  for_each = local.participant_users

  bucket = module.shared.csv_bucket_name
  role   = "roles/storage.bucketViewer"
  member = each.value
}

resource "google_project_iam_custom_role" "participant_connection_delegate" {
  project     = module.participant_project.project_id
  role_id     = "workshopConnectionDelegate"
  title       = "Workshop BigQuery connection delegate"
  permissions = ["bigquery.connections.delegate"]
}

resource "google_bigquery_connection_iam_member" "participant_delegate" {
  for_each = local.participant_users

  project       = module.participant_project.project_id
  location      = "EU"
  connection_id = module.pdf_extraction.connection_ids["2"]
  role          = google_project_iam_custom_role.participant_connection_delegate.name
  member        = each.value
}
