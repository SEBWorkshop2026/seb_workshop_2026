output "bucket_name" {
  value = google_storage_bucket.memos.name
}

output "connections" {
  description = "Connection reference per project number, as used in SQL (`<location>.<connection_id>`)."
  value       = { for number, c in google_bigquery_connection.gemini : number => "${lower(c.location)}.${c.connection_id}" }
}

output "connection_ids" {
  value = { for number, connection in google_bigquery_connection.gemini : number => connection.connection_id }
}

output "connection_service_accounts" {
  value = { for number, c in google_bigquery_connection.gemini : number => c.cloud_resource[0].service_account_id }
}
