output "projects" {
  value = merge({ for k, m in module.workshop : k => m.project_id }, { "2" = module.participant_project.project_id })
}

output "shared_project" {
  value = module.shared.project_id
}

output "shared_csv_bucket" {
  description = "Shared bucket for synthetic CSV source data."
  value       = module.shared.csv_bucket_name
}

output "participant_repositories" {
  description = "Dataform repository IDs by virtual participant slot in workshop project 02."
  value       = { for slot, repository in google_dataform_repository.participant : slot => repository.name }
}
