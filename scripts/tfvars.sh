#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
local_file="$root/terraform.tfvars"
remote_file="gs://${2:-ws2026-tfstate}/private/terraform.tfvars"

case "${1:-}" in
  upload)
    gcloud storage cp "$local_file" "$remote_file"
    ;;
  download)
    if [[ -e "$local_file" ]]; then
      echo "Refusing to overwrite $local_file. Move it aside first." >&2
      exit 1
    fi
    (
      umask 077
      gcloud storage cp "$remote_file" "$local_file"
    )
    ;;
  *)
    echo "Usage: $0 {upload|download} [bucket-name]" >&2
    exit 1
    ;;
esac
