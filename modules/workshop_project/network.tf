# Colab Enterprise (BigQuery Studio notebooks) default runtime uses the network
# named "default"; projects are created without one (auto_create_network = false).
resource "google_compute_network" "default" {
  project                 = google_project.this.project_id
  name                    = "default"
  auto_create_subnetworks = false

  depends_on = [google_project_service.apis]
}

resource "google_compute_subnetwork" "default" {
  project                  = google_project.this.project_id
  name                     = "default"
  region                   = var.notebook_region
  network                  = google_compute_network.default.id
  ip_cidr_range            = "10.0.0.0/24"
  private_ip_google_access = true
}

resource "google_colab_runtime_template" "default" {
  project      = google_project.this.project_id
  name         = "workshop"
  display_name = "Workshop"
  location     = var.notebook_region

  machine_spec {
    machine_type = "e2-standard-4"
  }

  network_spec {
    enable_internet_access = true
    network                = google_compute_network.default.id
    subnetwork             = google_compute_subnetwork.default.id
  }

  depends_on = [google_project_service.apis]
}
