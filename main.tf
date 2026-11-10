locals {
  project_numbers = [for i in range(1, var.project_count + 1) : tostring(i)]

  all_assigned_emails = distinct(flatten(values(var.assignments)))
  shared_viewers      = distinct(concat(local.all_assigned_emails, var.shared_project_viewers))
  enabled_apis        = setunion(toset(var.enabled_apis), toset(["bigquery.googleapis.com", "dataform.googleapis.com"]))

  admin_roles = toset([
    "roles/iam.workforcePoolAdmin",
    "roles/resourcemanager.organizationAdmin",
    "roles/resourcemanager.projectCreator",
    "roles/resourcemanager.projectMover",
    "roles/serviceusage.serviceUsageAdmin",
  ])
  admin_bindings = {
    for pair in setproduct(var.admin_users, local.admin_roles) :
    jsonencode(pair) => { email = pair[0], role = pair[1] }
  }
}

resource "google_organization_iam_member" "admins" {
  for_each = local.admin_bindings

  org_id = var.org_id
  role   = each.value.role
  member = "user:${each.value.email}"

  lifecycle {
    precondition {
      condition     = can(regex("^[0-9]+$", var.org_id))
      error_message = "Set org_id to a numeric organization ID when admin_users is nonempty."
    }
  }
}

module "workshop" {
  source   = "./modules/workshop_project"
  for_each = toset(local.project_numbers)

  project_id         = format("%s-%02d", var.name_prefix, tonumber(each.key))
  project_name       = format("Workshop %02d", tonumber(each.key))
  org_id             = var.org_id
  folder_id          = var.folder_id
  billing_account_id = var.billing_account_id
  apis               = local.enabled_apis
  budget_amount      = var.budget_amount
  budget_currency    = var.budget_currency
  budget_thresholds  = var.budget_alert_thresholds
  role               = var.participant_role
  members            = lookup(var.assignments, each.key, [])
}

module "shared" {
  source = "./modules/shared_project"

  project_id         = "${var.name_prefix}-shared"
  project_name       = "Workshop Shared"
  org_id             = var.org_id
  folder_id          = var.folder_id
  billing_account_id = var.billing_account_id
  apis               = local.enabled_apis
  budget_amount      = var.budget_amount
  budget_currency    = var.budget_currency
  budget_thresholds  = var.budget_alert_thresholds
  role               = var.shared_project_role
  members            = local.shared_viewers
}

resource "google_project_iam_member" "shared_bigquery_viewers" {
  for_each = merge(
    { for member in toset([for viewer in local.shared_viewers : can(regex("^(user|group|serviceAccount):", viewer)) ? viewer : "user:${viewer}"]) : "viewer:${member}" => member if var.shared_project_role != "roles/bigquery.dataViewer" },
    { for number, project in module.workshop : "project:${number}" => "serviceAccount:${project.dataform_service_account_email}" }
  )

  project = module.shared.project_id
  role    = "roles/bigquery.dataViewer"
  member  = each.value
}
