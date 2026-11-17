output "projects" {
  value = { for k, m in module.workshop : k => m.project_id }
}

output "shared_project" {
  value = module.shared.project_id
}

output "shared_csv_bucket" {
  description = "Shared bucket for synthetic CSV source data."
  value       = module.shared.csv_bucket_name
}

output "dataform_service_accounts" {
  description = "Select the corresponding account when creating a Dataform repository."
  value       = { for k, m in module.workshop : k => m.dataform_service_account_email }
}
