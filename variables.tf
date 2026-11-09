variable "admin_project_id" {
  description = "Existing project used for API quota/billing of budget calls (needs billingbudgets.googleapis.com enabled)."
  type        = string
}

variable "billing_account_id" {
  description = "Billing account ID (XXXXXX-XXXXXX-XXXXXX)."
  type        = string
}

variable "org_id" {
  description = "Organization ID. Set either org_id or folder_id."
  type        = string
  default     = null
}

variable "folder_id" {
  description = "Folder ID (digits only). Set either org_id or folder_id."
  type        = string
  default     = null
}

variable "name_prefix" {
  description = "Prefix for project IDs (must be globally unique, <= 20 chars)."
  type        = string
  default     = "ws2026"
}

variable "project_count" {
  type    = number
  default = 20
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
    "run.googleapis.com"
  ]
}

variable "participant_role" {
  description = "Role granted to a participant on their own project."
  type        = string
  default     = "roles/editor"
}

# Key = project number as string ("1".."20"); value = emails (user:, group: or
# serviceAccount: prefix optional; bare emails are treated as users).
variable "assignments" {
  description = "Map of project number => list of emails with access."
  type        = map(list(string))
  default     = {}
  validation {
    condition = alltrue([
      for k in keys(var.assignments) : can(tonumber(k)) && tonumber(k) >= 1 && tonumber(k) <= var.project_count
    ])
    error_message = "assignments keys must be project numbers between 1 and project_count."
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
