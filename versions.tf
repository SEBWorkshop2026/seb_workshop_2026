terraform {
  required_version = ">= 1.5"

  backend "gcs" {
    prefix = "terraform/workshop"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  # Budgets API requires a quota project when using user credentials.
  user_project_override = true
  billing_project       = var.admin_project_id
}
