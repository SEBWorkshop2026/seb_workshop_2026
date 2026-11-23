variable "admin_project_id" {
  description = "Existing project used for API quota/billing of budget calls (needs billingbudgets.googleapis.com enabled)."
  type        = string
}

variable "billing_account_id" {
  description = "Billing account ID (XXXXXX-XXXXXX-XXXXXX)."
  type        = string
}

variable "org_id" {
  description = "Organization ID. Required for admin_users even when projects are created under folder_id."
  type        = string
  default     = null
}

variable "folder_id" {
  description = "Folder ID (digits only). When set, projects are created in this folder instead of directly under org_id."
  type        = string
  default     = null
}

variable "admin_users" {
  description = "Google user account emails granted the administrator roles at the organization level."
  type        = set(string)
  default     = []

  validation {
    condition = alltrue([
      for email in var.admin_users : can(regex("^[^[:space:]@:]+@[^[:space:]@:]+$", email))
    ])
    error_message = "admin_users must contain bare user email addresses without whitespace or IAM prefixes."
  }
}

variable "name_prefix" {
  description = "Prefix for project IDs (must be globally unique, <= 20 chars)."
  type        = string
  default     = "ws2026"
}

variable "shared_csv_bucket_name" {
  description = "Optional globally unique name for the shared CSV bucket. Defaults to the shared project ID with a -csv suffix."
  type        = string
  default     = null
}

variable "project_count" {
  type    = number
  default = 20

  validation {
    condition     = var.project_count >= 2 && var.project_count == floor(var.project_count)
    error_message = "project_count must be a whole number of at least 2."
  }
}

variable "participant_count" {
  description = "Number of virtual participant slots in workshop project 02."
  type        = number
  default     = 50

  validation {
    condition     = var.participant_count >= 1 && var.participant_count <= 1000 && var.participant_count == floor(var.participant_count)
    error_message = "participant_count must be a whole number between 1 and 1000."
  }
}

variable "budget_amount" {
  description = "Budget per workshop project."
  type        = number
  default     = 50
}

variable "budget_currency" {
  type    = string
  default = "EUR"
}

variable "budget_alert_thresholds" {
  type    = list(number)
  default = [0.5, 0.9, 1.0]
}

variable "enabled_apis" {
  description = "Additional APIs enabled in every workshop project. BigQuery and Dataform are always enabled."
  type        = list(string)
  default = [
    "compute.googleapis.com",
    "storage.googleapis.com",
    "run.googleapis.com",
    "aiplatform.googleapis.com"
  ]
}

variable "notebook_region" {
  description = "Region of the subnet in each workshop project's \"default\" VPC, used by BigQuery Studio (Colab Enterprise) notebook runtimes."
  type        = string
  default     = "europe-central2"
}

variable "dataform_region" {
  description = "Region for participant Dataform repositories."
  type        = string
  default     = "europe-west1"
}

variable "participant_role" {
  description = "Role granted to a participant on their own project."
  type        = string
  default     = "roles/editor"
}

# Keys identify virtual participant slots.
variable "assignments" {
  description = "Map of participant slot => zero or one Google user email."
  type        = map(list(string))
  default     = {}
  validation {
    condition = alltrue([
      for k, members in var.assignments :
      can(regex("^[1-9][0-9]*$", k)) && try(tonumber(k) <= var.participant_count, false) &&
      length(members) <= 1 &&
      alltrue([for member in members : can(regex("^(user:)?[^[:space:]@:]+@[^[:space:]@:]+$", member))])
    ])
    error_message = "assignments must use participant slots between 1 and participant_count, each with at most one user email."
  }
  validation {
    condition = length(distinct([
      for member in flatten(values(var.assignments)) : lower(trimprefix(member, "user:"))
    ])) == length(flatten(values(var.assignments)))
    error_message = "A user cannot be assigned to more than one participant slot."
  }
}

variable "shared_project_viewers" {
  description = "Extra emails with read access to the shared project (all assigned emails are always included)."
  type        = list(string)
  default     = []
}

variable "shared_project_role" {
  type    = string
  default = "roles/viewer"
}
