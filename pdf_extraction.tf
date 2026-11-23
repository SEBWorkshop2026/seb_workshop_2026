# PDF AI extraction session (Andrej). Copy this file to the repository root next to main.tf and the
# module directory to modules/pdf_extraction. Uses the existing workshop and shared modules.

variable "credit_memo_bucket_name" {
  description = "Optional globally unique name for the credit memo bucket. Defaults to <shared-project-id>-credit-memos."
  type        = string
  default     = null
}

variable "credit_memo_source_dir" {
  description = "Local directory with the generated memos (pdf/*.pdf and ground_truth.csv). Null creates the bucket without uploading."
  type        = string
  default     = null
}

module "pdf_extraction" {
  source = "./modules/pdf_extraction"

  shared_project_id = module.shared.project_id
  bucket_name       = var.credit_memo_bucket_name
  memo_source_dir   = var.credit_memo_source_dir
  extra_viewers     = var.shared_project_viewers

  participant_projects = merge({
    for number, project in module.workshop : number => {
      project_id = project.project_id
      members    = contains(["1", "3"], number) ? [] : lookup(var.assignments, number, [])
    }
    }, {
    "2" = {
      project_id = module.participant_project.project_id
      members    = flatten(values(var.assignments))
    }
  })
}

output "credit_memo_bucket" {
  description = "Bucket with the credit memo PDFs (pdf/) and labels (ground_truth.csv)."
  value       = module.pdf_extraction.bucket_name
}

output "credit_memo_connections" {
  description = "BigQuery connection per project number, as referenced in SQL."
  value       = module.pdf_extraction.connections
}
