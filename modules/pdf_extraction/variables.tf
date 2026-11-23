variable "shared_project_id" {
  description = "Shared workshop project that hosts the credit memo bucket."
  type        = string
}

variable "bucket_name" {
  description = "Optional globally unique bucket name. Defaults to the shared project ID with a -credit-memos suffix."
  type        = string
  default     = null
}

variable "location" {
  description = "Location of the bucket and the BigQuery connections. Must match the participants' datasets (EU)."
  type        = string
  default     = "EU"
}

variable "connection_id" {
  description = "BigQuery connection ID created in every participant project (referenced as `eu.<id>` in SQL)."
  type        = string
  default     = "credit_memos"
}

variable "dataset_id" {
  description = "BigQuery dataset created in every participant project for the credit memo object table and extraction results."
  type        = string
  default     = "credit_memos"
}

variable "memo_source_dir" {
  description = "Local directory with pdf/*.pdf and ground_truth.csv (output of gen_memos.py). Null skips the upload."
  type        = string
  default     = null
}

variable "participant_projects" {
  description = "Workshop projects keyed by project number: project ID, Dataform execution account and assigned members."
  type = map(object({
    project_id               = string
    dataform_service_account = string
    members                  = list(string)
  }))
}

variable "extra_viewers" {
  description = "Additional emails with read access to the memo archive (bare emails are treated as users)."
  type        = list(string)
  default     = []
}
