output "project_id" {
  value = google_project.this.project_id
}

output "dataform_service_account_email" {
  value = google_service_account.dataform.email
}
