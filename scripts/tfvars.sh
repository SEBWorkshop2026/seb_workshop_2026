#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
remote_dir="gs://${2:-ws2026-tfstate}/private"

case "${1:-}" in
  upload)
    shopt -s nullglob
    files=()
    for file in "$root"/*.tfvars "$root"/*.tfvars.json; do
      [[ -f "$file" ]] && files+=("$file")
    done
    if (( ${#files[@]} == 0 )); then
      echo "No tfvars files found in $root" >&2
      exit 1
    fi
    gcloud storage cp "${files[@]}" "$remote_dir/"
    ;;
  download)
    listing="$(gcloud storage ls "$remote_dir/*")"
    objects=()
    while IFS= read -r object; do
      [[ "$object" == "$remote_dir/"* ]] || continue
      name="${object#"$remote_dir/"}"
      if [[ "$name" != */* && ( "$name" == *.tfvars || "$name" == *.tfvars.json ) ]]; then
        objects+=("$object")
      fi
    done <<< "$listing"
    if (( ${#objects[@]} == 0 )); then
      echo "No tfvars files found in $remote_dir" >&2
      exit 1
    fi
    for object in "${objects[@]}"; do
      local_file="$root/${object##*/}"
      if [[ -d "$local_file" ]]; then
        echo "Cannot download to a directory: $local_file" >&2
        exit 1
      fi
    done
    umask 077
    for object in "${objects[@]}"; do
      local_file="$root/${object##*/}"
      temp_file="$(mktemp "$root/.tfvars-download.XXXXXX")"
      trap 'rm -f -- "$temp_file"' EXIT
      gcloud storage cp "$object" "$temp_file"
      mv -f -- "$temp_file" "$local_file"
      trap - EXIT
    done
    ;;
  *)
    echo "Usage: $0 {upload|download} [bucket-name]" >&2
    exit 1
    ;;
esac
