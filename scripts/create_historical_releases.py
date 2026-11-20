#!/usr/bin/env python3
"""Create Dataform releases for the sample data's monthly snapshots."""

import argparse
import json
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

SNAPSHOT_PERIODS = [
    *(f"{year}-{month:02d}" for year in (2024, 2025) for month in range(1, 13)),
    "2026-01",
]


def request(method, path, token, *, params=None, body=None):
    url = f"https://dataform.googleapis.com/v1/{path}"
    if params:
        url += "?" + urlencode(params)
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    try:
        with urlopen(Request(url, data=data, headers=headers, method=method), timeout=60) as response:
            result = response.read()
            return json.loads(result) if result else {}
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Dataform {method} {path} failed (HTTP {error.code}): {detail}") from error


def create_releases(project, location, repository, csv_bucket, token):
    parent = "/".join([
        "projects", quote(project, safe=""),
        "locations", quote(location, safe=""),
        "repositories", quote(repository, safe=""),
    ])
    for period in SNAPSHOT_PERIODS:
        release_id = f"historical-{period}"
        release_name = f"{parent}/releaseConfigs/{release_id}"
        config = {
            "gitCommitish": "main",
            "codeCompilationConfig": {
                "defaultDatabase": project,
                "vars": {"reporting_period": period, "csv_bucket": csv_bucket},
            },
        }
        try:
            release = request("GET", release_name, token)
        except RuntimeError as error:
            if not isinstance(error.__cause__, HTTPError) or error.__cause__.code != 404:
                raise
            release = request(
                "POST", f"{parent}/releaseConfigs", token,
                params={"releaseConfigId": release_id}, body=config,
            )

        if (
            release.get("gitCommitish") != config["gitCommitish"]
            or release.get("codeCompilationConfig") != config["codeCompilationConfig"]
            or release.get("cronSchedule")
            or release.get("disabled")
        ):
            raise ValueError(f"{release_name} differs from the requested unscheduled configuration; not modifying it")

        result = request(
            "POST", f"{parent}/compilationResults", token,
            body={"releaseConfig": release_name},
        )
        if result.get("compilationErrors"):
            raise RuntimeError(f"{period}: compilation failed: {json.dumps(result['compilationErrors'])}")
        result_name = result.get("name")
        if not result_name:
            raise RuntimeError(f"{period}: compilation response did not contain a result name")
        request(
            "PATCH", release_name, token,
            params={"updateMask": "releaseCompilationResult"},
            body={
                "name": release_name,
                "gitCommitish": release["gitCommitish"],
                "releaseCompilationResult": result_name,
            },
        )
        print(f"{period}: released {result_name} (commit {result.get('resolvedGitCommitSha', 'not reported')})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="ws2026-01", help="Participant project ID")
    parser.add_argument("--location", default="europe-west1", help="Dataform repository location")
    parser.add_argument("--repository", default="first_repo", help="Dataform repository ID")
    parser.add_argument("--csv-bucket", default="ws2026-shared-csv", help="Shared CSV bucket name")
    args = parser.parse_args()

    token = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        check=True, stdout=subprocess.PIPE, text=True,
    ).stdout.strip()
    if not token:
        raise ValueError("gcloud returned an empty access token")
    create_releases(args.project, args.location, args.repository, args.csv_bucket, token)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, URLError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
