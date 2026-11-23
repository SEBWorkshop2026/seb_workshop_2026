locals {
  participant_members = toset([
    for member in var.members : can(regex("^(user|group|serviceAccount):", member)) ? member : "user:${member}"
  ])
  # connectionAdmin carries bigquery.connections.delegate, required for object tables and remote
  # models created WITH CONNECTION (connectionUser and basic roles lack it).
  dataform_bigquery_roles = toset([
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/bigquery.connectionAdmin",
  ])
  dataform_participant_roles = setsubtract(
    setunion(local.dataform_bigquery_roles, toset(["roles/dataform.editor"])),
    toset([var.role]),
  )
  dataform_participant_bindings = {
    for pair in setproduct(local.participant_members, local.dataform_participant_roles) :
    jsonencode(pair) => { member = pair[0], role = pair[1] }
  }
}

resource "google_project_iam_member" "dataform_participants" {
  for_each = local.dataform_participant_bindings

  project = google_project.this.project_id
  role    = each.value.role
  member  = each.value.member
}
