output "project_id" {
  value = google_project.this.project_id
}

output "csv_bucket_name" {
  value = google_storage_bucket.csv.name
}
