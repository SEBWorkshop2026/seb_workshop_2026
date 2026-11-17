#!/usr/bin/env python3
"""Upload the local Dataform project to a Dataform development workspace."""

import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="ws2026-01")
    parser.add_argument("--location", default="europe-west1")
    parser.add_argument("--repository", default="first_repo")
    parser.add_argument("--workspace", default="dev_workspace_1")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace differing files already present in the workspace.",
    )
    args = parser.parse_args()

    source = Path(__file__).resolve().parent.parent / "dataform"
    if not (source / "workflow_settings.yaml").is_file():
        raise ValueError(f"Dataform project not found: {source}")

    def walk_error(error):
        raise error

    local_files = {}
    for root, dirs, filenames in os.walk(source, followlinks=False, onerror=walk_error):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "node_modules")
        for name in dirs + filenames:
            path = Path(root) / name
            if not name.startswith(".") and path.is_symlink():
                raise ValueError(f"Refusing to upload symbolic link: {path}")
        for name in sorted(filenames):
            if not name.startswith("."):
                path = Path(root) / name
                local_files[path.relative_to(source).as_posix()] = path.read_bytes()

    token = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    if not token:
        raise ValueError("gcloud returned an empty access token")

    workspace = "/".join(
        [
            "projects", quote(args.project, safe=""),
            "locations", quote(args.location, safe=""),
            "repositories", quote(args.repository, safe=""),
            "workspaces", quote(args.workspace, safe=""),
        ]
    )
    base_url = f"https://dataform.googleapis.com/v1/{workspace}"

    def request(action, *, params=None, body=None):
        url = f"{base_url}:{action}"
        if params:
            url += "?" + urlencode(params)
        headers = {"Authorization": f"Bearer {token}"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        req = Request(url, data=data, headers=headers)
        try:
            with urlopen(req, timeout=60) as response:
                response_body = response.read()
                return json.loads(response_body) if response_body else {}
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Dataform {action} failed (HTTP {error.code}): {detail}") from error

    remote_files = set()
    remote_dirs = {""}
    pending = [""]
    while pending:
        directory = pending.pop()
        page_token = ""
        while True:
            params = {}
            if directory:
                params["path"] = directory
            if page_token:
                params["pageToken"] = page_token
            result = request("queryDirectoryContents", params=params)
            for entry in result.get("directoryEntries", []):
                if "file" in entry:
                    remote_files.add(entry["file"])
                elif "directory" in entry:
                    remote_dirs.add(entry["directory"])
                    pending.append(entry["directory"])
                else:
                    raise ValueError(f"Unexpected Dataform directory entry: {entry}")
            page_token = result.get("nextPageToken", "")
            if not page_token:
                break

    local_dirs = set()
    for path in local_files:
        parent = Path(path).parent
        while parent != Path("."):
            local_dirs.add(parent.as_posix())
            parent = parent.parent
    for directory in local_dirs:
        if directory in remote_files:
            raise ValueError(f"Workspace file blocks local directory: {directory}")
    for path in local_files:
        if path in remote_dirs:
            raise ValueError(f"Workspace directory blocks local file: {path}")

    changed = {}
    for path, contents in local_files.items():
        if path in remote_files:
            result = request("readFile", params={"path": path})
            existing = base64.b64decode(result.get("fileContents", ""), validate=True)
            if existing == contents:
                continue
        changed[path] = contents

    conflicts = sorted(set(changed) & remote_files)
    if conflicts and not args.overwrite:
        print("Workspace files differ; no files were uploaded:", file=sys.stderr)
        for path in conflicts:
            print(f"  {path}", file=sys.stderr)
        raise ValueError("Review the workspace changes and rerun with --overwrite to replace them.")

    extra_files = sorted(
        path for path in remote_files - local_files.keys()
        if path.startswith(("definitions/", "includes/")) and path.endswith((".sqlx", ".js"))
    )
    if extra_files:
        print("Workspace code files not present locally will remain:")
        for path in extra_files:
            print(f"  {path}")

    for directory in sorted(local_dirs - remote_dirs, key=lambda path: (path.count("/"), path)):
        request("makeDirectory", body={"path": directory})
        print(f"Created directory {directory}")
    for path, contents in sorted(changed.items()):
        request(
            "writeFile",
            body={"path": path, "contents": base64.b64encode(contents).decode("ascii")},
        )
        print(f"Uploaded {path}")

    print(f"Done: {len(changed)} file(s) uploaded to {workspace}. Changes are not committed.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, URLError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
