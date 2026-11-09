terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
    }
  }
}

resource "google_project" "this" {
  project_id          = var.project_id
  name                = var.project_name
  org_id              = var.folder_id == null ? var.org_id : null
  folder_id           = var.folder_id
  billing_account     = var.billing_account_id
  auto_create_network = false
  deletion_policy     = "DELETE"
}

resource "google_project_service" "apis" {
  for_each           = toset(var.apis)
  project            = google_project.this.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_project_iam_member" "members" {
  for_each = toset(var.members)
  project  = google_project.this.project_id
  role     = var.role
  member   = can(regex("^(user|group|serviceAccount):", each.value)) ? each.value : "user:${each.value}"
}

resource "google_billing_budget" "this" {
  billing_account = var.billing_account_id
  display_name    = "${var.project_id}-budget"

  budget_filter {
    projects = ["projects/${google_project.this.number}"]
  }

  amount {
    specified_amount {
      currency_code = var.budget_currency
      units         = tostring(var.budget_amount)
    }
  }

  dynamic "threshold_rules" {
    for_each = var.budget_thresholds
    content {
      threshold_percent = threshold_rules.value
    }
  }
}
