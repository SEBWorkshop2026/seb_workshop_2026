output "projects" {
  value = { for k, m in module.workshop : k => m.project_id }
}

output "shared_project" {
  value = module.shared.project_id
}
