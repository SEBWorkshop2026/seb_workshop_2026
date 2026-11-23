variable "project_id" { type = string }
variable "project_name" { type = string }
variable "org_id" {
  type    = string
  default = null
}
variable "folder_id" {
  type    = string
  default = null
}
variable "billing_account_id" { type = string }
variable "apis" { type = list(string) }
variable "notebook_region" { type = string }
variable "budget_amount" { type = number }
variable "budget_currency" { type = string }
variable "budget_thresholds" { type = list(number) }
variable "role" { type = string }
variable "bigquery_datasets" {
  description = "BigQuery datasets created in the project for the Dataform pipeline."
  type        = list(string)
  default     = ["external", "bronze", "silver", "gold"]
}
variable "bigquery_location" {
  description = "Location of the BigQuery datasets."
  type        = string
  default     = "EU"
}
variable "members" {
  type    = list(string)
  default = []
}
