locals {
  project_numbers = [for i in range(1, var.project_count + 1) : tostring(i)]

  all_assigned_emails = distinct(flatten(values(var.assignments)))
  shared_viewers      = distinct(concat(local.all_assigned_emails, var.shared_project_viewers))
}

module "workshop" {
  source   = "./modules/workshop_project"
  for_each = toset(local.project_numbers)

  project_id         = format("%s-%02d", var.name_prefix, tonumber(each.key))
  project_name       = format("Workshop %02d", tonumber(each.key))
  org_id             = var.org_id
  folder_id          = var.folder_id
  billing_account_id = var.billing_account_id
  apis               = var.enabled_apis
  budget_amount      = var.budget_amount
  budget_currency    = var.budget_currency
  budget_thresholds  = var.budget_alert_thresholds
  role               = var.participant_role
  members            = lookup(var.assignments, each.key, [])
}

module "shared" {
  source = "./modules/workshop_project"

  project_id         = "${var.name_prefix}-shared"
  project_name       = "Workshop Shared"
  org_id             = var.org_id
  folder_id          = var.folder_id
  billing_account_id = var.billing_account_id
  apis               = var.enabled_apis
  budget_amount      = var.budget_amount
  budget_currency    = var.budget_currency
  budget_thresholds  = var.budget_alert_thresholds
  role               = var.shared_project_role
  members            = local.shared_viewers
}
