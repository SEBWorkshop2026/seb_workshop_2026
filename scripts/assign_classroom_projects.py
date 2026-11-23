#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "google-api-python-client",
#     "google-auth",
#     "google-auth-httplib2",
# ]
# ///
"""Generate stable virtual participant assignments from a Google Classroom roster."""

import argparse
import getpass
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import quote
import webbrowser

from google.auth.exceptions import GoogleAuthError
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import build_http


SCOPES = (
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
    "https://www.googleapis.com/auth/classroom.profile.emails",
)
PLAYGROUND_URL = (
    "https://developers.google.com/oauthplayground/#step1&scopes="
    + quote(" ".join(SCOPES), safe="")
    + "&useDefaultOauthCred=unchecked&oauthEndpointSelect=Google"
    + "&response_type=code&accessType=offline&prompt=consent"
)


def authorize(path):
    if not sys.stdin.isatty():
        raise ValueError("Run this command in an interactive terminal to paste the token privately")

    print(f"OAuth Playground: {PLAYGROUND_URL}")
    if not webbrowser.open(PLAYGROUND_URL):
        print("Could not open a browser; open the link above manually.")
    print("In the Playground, click Authorize APIs, sign in as the teacher and grant access.")
    print("Then click Exchange authorization code for tokens and copy the Access token.")
    token = getpass.getpass("Paste the access token (input hidden): ").strip()
    if not token or any(char.isspace() for char in token):
        raise ValueError("Paste the access token only, without spaces or other text")

    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump({"access_token": token}, output)
            output.write("\n")
        os.replace(temp_name, path)
    finally:
        Path(temp_name).unlink(missing_ok=True)
    print(f"Saved access token to {path}")
    return token


def load_token(path):
    with path.open(encoding="utf-8") as credential_file:
        credential_data = json.load(credential_file)
    if not isinstance(credential_data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    token = credential_data.get("access_token")
    if not isinstance(token, str) or not token.strip():
        raise ValueError(f"Set a nonempty access_token in {path}")
    return token.strip()


def classroom_service(token):
    http = AuthorizedHttp(Credentials(token=token), http=build_http(), max_refresh_attempts=0)
    return build("classroom", "v1", http=http)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--class-name", required=True, help="Exact name of an active class you teach")
    parser.add_argument("--credentials", type=Path, default=Path("credential.json"), help="JSON file containing an access_token")
    parser.add_argument("--authorize", action="store_true", help="Replace the saved token using OAuth Playground")
    parser.add_argument("--participant-count", type=int, default=50, help="Available participant slots (default: 50)")
    parser.add_argument("--output", type=Path, default=Path("classroom-assignments.auto.tfvars.json"))
    args = parser.parse_args()

    if args.output.resolve() == args.credentials.resolve():
        parser.error("Output and credentials must be different files")
    if args.participant_count < 1:
        parser.error("--participant-count must be positive")

    authorized = args.authorize
    if authorized:
        token = authorize(args.credentials)
    else:
        try:
            token = load_token(args.credentials)
        except FileNotFoundError:
            token = authorize(args.credentials)
            authorized = True

    try:
        students = classroom_students(classroom_service(token), args.class_name)
    except HttpError as error:
        if error.resp.status != 401 or authorized:
            raise
        print("The saved Classroom token is expired or invalid; authorization is required.")
        token = authorize(args.credentials)
        students = classroom_students(classroom_service(token), args.class_name)
    assignments = make_assignments(students, read_assignments(args.output), args.participant_count)
    write_assignments(args.output, assignments)
    print(f"Wrote {len(students)} student assignments to {args.output}")


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


def read_assignments(path):
    try:
        with path.open(encoding="utf-8") as assignment_file:
            data = json.load(assignment_file)
    except FileNotFoundError:
        return {}
    if not isinstance(data, dict) or set(data) != {"assignments"} or not isinstance(data["assignments"], dict):
        raise ValueError(f"Expected an assignments object in {path}; refusing to overwrite it")
    return data["assignments"]


def make_assignments(students, existing=None, participant_count=50):
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
    by_email = {email.casefold(): email for email in emails}
    assigned = set()
    result = {}
    for slot, members in (existing or {}).items():
        if not isinstance(slot, str) or not re.fullmatch(r"[1-9][0-9]*", slot) or int(slot) > participant_count:
            raise ValueError(f"Invalid existing participant slot: {slot!r}")
        if not isinstance(members, list) or len(members) > 1:
            raise ValueError(f"Existing participant slot {slot} must contain at most one user")
        result[slot] = []
        if members:
            member = members[0]
            if not isinstance(member, str):
                raise ValueError(f"Invalid user in participant slot {slot}")
            email = member.removeprefix("user:")
            if not re.fullmatch(r"[^\s@:]+@[^\s@:]+", email):
                raise ValueError(f"Invalid user in participant slot {slot}")
            key = email.casefold()
            if key in assigned:
                raise ValueError(f"Duplicate user in existing assignments: {email}")
            assigned.add(key)
            if key in by_email:
                result[slot] = [by_email[key]]

    next_slot = max((int(slot) for slot in result), default=0) + 1
    for key in sorted(by_email.keys() - assigned):
        if next_slot > participant_count:
            raise ValueError("Not enough unused participant slots; increase participant_count and --participant-count")
        result[str(next_slot)] = [by_email[key]]
        next_slot += 1
    return dict(sorted(result.items(), key=lambda item: int(item[0])))


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
    except (OSError, ValueError, GoogleAuthError, HttpError, webbrowser.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.", file=sys.stderr)
        sys.exit(1)
