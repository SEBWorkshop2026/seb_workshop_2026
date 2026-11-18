#!/usr/bin/env python3
"""Run historical Dataform releases sequentially."""

import argparse
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.parse import quote

from create_historical_releases import SNAPSHOT_PERIODS, request


def run_releases(parent, periods, api):
    results = []
    for period in periods:
        release_name = f"{parent}/releaseConfigs/historical-{period}"
        release = api("GET", release_name)
        if release.get("codeCompilationConfig", {}).get("vars", {}).get("reporting_period") != period:
            raise ValueError(f"{release_name} does not specify reporting_period {period}")
        result = release.get("releaseCompilationResult")
        if not result or not result.startswith(f"{parent}/compilationResults/"):
            raise ValueError(f"{release_name} has no live compilation result in this repository")
        results.append((period, result))

    for period, result in results:
        invocation = api("POST", f"{parent}/workflowInvocations", body={"compilationResult": result})
        name = invocation.get("name")
        if not name or not name.startswith(f"{parent}/workflowInvocations/"):
            raise RuntimeError(f"{period}: invocation response has no valid name; check Dataform before retrying")
        print(f"{period}: started {name}", flush=True)
        while True:
            invocation = api("GET", name)
            state = invocation.get("state")
            if state == "SUCCEEDED":
                print(f"{period}: succeeded", flush=True)
                break
            if state not in ("RUNNING", "CANCELING"):
                raise RuntimeError(f"{period}: {name} ended or returned unexpected state: {state}")
            time.sleep(10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="ws2026-01", help="Participant project ID")
    parser.add_argument("--location", default="europe-west1", help="Dataform repository location")
    parser.add_argument("--repository", default="first_repo", help="Dataform repository ID")
    parser.add_argument(
        "--start-period", choices=SNAPSHOT_PERIODS, default=SNAPSHOT_PERIODS[0],
        help="First period to execute, inclusive (default: 2024-01)",
    )
    args = parser.parse_args()
    parent = "/".join([
        "projects", quote(args.project, safe=""),
        "locations", quote(args.location, safe=""),
        "repositories", quote(args.repository, safe=""),
    ])

    token = ""
    refresh_at = 0

    def api(method, path, *, body=None):
        nonlocal token, refresh_at
        if time.monotonic() >= refresh_at:
            token = subprocess.run(
                ["gcloud", "auth", "print-access-token"],
                check=True, stdout=subprocess.PIPE, text=True,
            ).stdout.strip()
            if not token:
                raise ValueError("gcloud returned an empty access token")
            refresh_at = time.monotonic() + 45 * 60
        return request(method, path, token, body=body)

    run_releases(parent, SNAPSHOT_PERIODS[SNAPSHOT_PERIODS.index(args.start_period):], api)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, URLError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("Interrupted; an invocation may still be running. Check Dataform before retrying.", file=sys.stderr)
        sys.exit(130)
