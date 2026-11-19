#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "google-api-python-client",
#     "google-auth",
# ]
# ///
"""Generate Terraform project assignments from an active Google Classroom roster."""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from google.auth.exceptions import GoogleAuthError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--class-name", required=True, help="Exact name of an active class you teach")
    parser.add_argument("--credentials", type=Path, default=Path("credential.json"), help="JSON file containing an access_token")
    parser.add_argument("--output", type=Path, default=Path("classroom-assignments.auto.tfvars.json"))
    args = parser.parse_args()

    if args.output.resolve() == args.credentials.resolve():
        parser.error("Output and credentials must be different files")

    with args.credentials.open(encoding="utf-8") as credential_file:
        credential_data = json.load(credential_file)
    if not isinstance(credential_data, dict):
        raise ValueError(f"Expected a JSON object in {args.credentials}")
    token = credential_data.get("access_token")
    if not isinstance(token, str) or not token.strip():
        raise ValueError(f"Set a nonempty access_token in {args.credentials}")
    credentials = Credentials(token=token.strip())
    service = build("classroom", "v1", credentials=credentials)
    assignments = make_assignments(classroom_students(service, args.class_name))
    write_assignments(args.output, assignments)
    print(f"Wrote {len(assignments)} student assignments to {args.output}")


def classroom_students(service, class_name):
    courses = []
    token = None
    while True:
        response = service.courses().list(
            teacherId="me", courseStates=["ACTIVE"], pageSize=100, pageToken=token
        ).execute()
        courses.extend(course for course in response.get("courses", []) if course["name"] == class_name)
        token = response.get("nextPageToken")
        if not token:
            break
    if not courses:
        raise ValueError(f"No active class named {class_name!r} found for this teacher")
    if len(courses) != 1:
        raise ValueError(f"Multiple active classes named {class_name!r}; use a unique class name")

    students = []
    token = None
    while True:
        response = service.courses().students().list(
            courseId=courses[0]["id"], pageSize=100, pageToken=token
        ).execute()
        students.extend(response.get("students", []))
        token = response.get("nextPageToken")
        if not token:
            return students


def make_assignments(students):
    if not students:
        raise ValueError("Class roster is empty; refusing to generate empty assignments")

    emails = []
    seen = set()
    for student in students:
        email = student.get("profile", {}).get("emailAddress", "")
        if not isinstance(email, str) or not re.fullmatch(r"[^\s@:]+@[^\s@:]+", email):
            raise ValueError("A student has a missing or invalid email address; check Classroom permissions")
        if email.casefold() in seen:
            raise ValueError(f"Duplicate student email: {email}")
        seen.add(email.casefold())
        emails.append(email)
    return {str(index): [email] for index, email in enumerate(sorted(emails, key=str.casefold), 1)}


def write_assignments(path, assignments):
    content = json.dumps({"assignments": assignments}, indent=2) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(content)
        os.replace(temp_name, path)
    finally:
        Path(temp_name).unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, GoogleAuthError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
