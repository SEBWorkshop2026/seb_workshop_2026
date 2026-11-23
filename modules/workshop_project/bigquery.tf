# Datasets used by the Dataform pipeline (external tables, bronze, silver and gold layers).
resource "google_bigquery_dataset" "this" {
  for_each = toset(var.bigquery_datasets)

  project                    = google_project.this.project_id
  dataset_id                 = each.value
  location                   = var.bigquery_location
  delete_contents_on_destroy = true

  depends_on = [google_project_service.apis]
}
