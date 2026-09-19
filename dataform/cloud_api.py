"""Provision, sync, run, and inspect the dedicated APAC Dataform workflow."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


PROJECT = "bq-dataform-sg"
LOCATION = "asia-southeast1"
REPOSITORY = "apac-metasearch-performance"
WORKSPACE = "development"
RUNNER = "apac-metasearch-dataform@bq-dataform-sg.iam.gserviceaccount.com"
ROOT = Path(__file__).resolve().parent
REPO_PATH = f"projects/{PROJECT}/locations/{LOCATION}/repositories/{REPOSITORY}"
BASE = "https://dataform.googleapis.com/v1/"
LAST_RUN = ROOT / ".last_invocation.json"
DASHBOARD_STATUS = ROOT.parent / "bi" / "snapshot" / "dataform_workflow_status.csv"
PROBLEM_STATES = {"FAILED", "CANCELLED", "SKIPPED"}


def access_token() -> str:
    gcloud = shutil.which("gcloud.cmd" if os.name == "nt" else "gcloud")
    if not gcloud:
        raise RuntimeError("gcloud CLI not found")
    return subprocess.run([gcloud, "auth", "print-access-token"], check=True,
                          capture_output=True, text=True).stdout.strip()


def request(method: str, url: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Authorization": f"Bearer {access_token()}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url}: HTTP {exc.code}: {detail}") from exc


def grant_dataset_access() -> None:
    for dataset, role in (
        ("apac_meta_bronze", "READER"),
        ("apac_meta_silver", "WRITER"),
        ("apac_meta_gold", "WRITER"),
        ("apac_meta_assertions", "WRITER"),
    ):
        url = f"https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}/datasets/{dataset}"
        current = request("GET", url)
        access = current["access"]
        if not any(a.get("userByEmail") == RUNNER and a.get("role") == role for a in access):
            access.append({"role": role, "userByEmail": RUNNER})
            request("PATCH", url, {"access": access})
        print(f"{dataset}: {role} for dedicated runner")


def provision_and_sync() -> None:
    repository_url = BASE + REPO_PATH
    try:
        request("GET", repository_url)
    except RuntimeError as exc:
        if "HTTP 404" not in str(exc):
            raise
        request("POST", BASE + f"projects/{PROJECT}/locations/{LOCATION}/repositories"
                + f"?repositoryId={REPOSITORY}", {"serviceAccount": RUNNER})
        print(f"Created Dataform repository {REPOSITORY}")
    workspace_path = f"{REPO_PATH}/workspaces/{WORKSPACE}"
    try:
        request("GET", BASE + workspace_path)
    except RuntimeError as exc:
        if "HTTP 404" not in str(exc):
            raise
        request("POST", BASE + f"{REPO_PATH}/workspaces?workspaceId={WORKSPACE}", {})
        print(f"Created workspace {WORKSPACE}")
    files = [ROOT / "workflow_settings.yaml", *sorted((ROOT / "definitions").glob("*.sqlx"))]
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        request("POST", BASE + workspace_path + ":writeFile",
                {"path": relative, "contents": encoded})
    print(f"Synced {len(files)} Dataform files")


def run() -> None:
    compilation = request("POST", BASE + f"{REPO_PATH}/compilationResults",
                          {"workspace": f"{REPO_PATH}/workspaces/{WORKSPACE}"})
    errors = compilation.get("compilationErrors", [])
    if errors:
        raise RuntimeError("Compilation failed: " + json.dumps(errors, indent=2))
    print("Compilation passed:", compilation["name"])
    invocation = request("POST", BASE + f"{REPO_PATH}/workflowInvocations",
                         {"compilationResult": compilation["name"]})
    LAST_RUN.write_text(json.dumps({"name": invocation["name"]}, indent=2), encoding="utf-8")
    print("Started invocation:", invocation["name"])


def invocation_details() -> tuple[str, dict, list[dict]]:
    if not LAST_RUN.exists():
        raise RuntimeError("No local invocation record; run the workflow first")
    name = json.loads(LAST_RUN.read_text(encoding="utf-8"))["name"]
    invocation = request("GET", BASE + name)
    actions = request("GET", BASE + name + ":query").get("workflowInvocationActions", [])
    return name, invocation, actions


def status() -> None:
    _, invocation, actions = invocation_details()
    print("Invocation state:", invocation.get("state"))
    failed = []
    for action in actions:
        target = action.get("target", {}).get("name", "unknown")
        state = action.get("state", "unknown")
        if state in PROBLEM_STATES:
            failed.append((target, state, action.get("failureReason", "")))
    print(f"Actions: {len(actions)}; failed/skipped: {len(failed)}")
    for item in failed:
        print(*item, sep=" | ")
    if invocation.get("state") != "SUCCEEDED":
        sys.exit(1)


def dashboard_status() -> None:
    """Write the latest Dataform run summary for the Power BI quality page."""
    name, invocation, actions = invocation_details()
    assertion_actions = [
        action for action in actions
        if action.get("target", {}).get("schema") == "apac_meta_assertions"
    ]
    non_succeeded = [action for action in actions if action.get("state") != "SUCCEEDED"]
    problem_actions = [action for action in actions if action.get("state") in PROBLEM_STATES]
    problem_assertions = [action for action in assertion_actions if action.get("state") in PROBLEM_STATES]
    invocation_state = invocation.get("state", "UNKNOWN")
    if invocation_state == "SUCCEEDED" and not non_succeeded:
        gate_status = "PASS"
    elif invocation_state in PROBLEM_STATES or problem_actions:
        gate_status = "FAIL"
    else:
        gate_status = "UNKNOWN"
    timing = invocation.get("invocationTiming", {})
    row = {
        "invocation_id": name.rsplit("/", 1)[-1],
        "invocation_state": invocation_state,
        "workflow_gate_status": gate_status,
        "workflow_start_utc": timing.get("startTime", ""),
        "workflow_end_utc": timing.get("endTime", ""),
        "total_actions": len(actions),
        "non_succeeded_actions": len(non_succeeded),
        "problem_actions": len(problem_actions),
        "assertion_actions": len(assertion_actions),
        "problem_assertion_actions": len(problem_assertions),
    }
    DASHBOARD_STATUS.parent.mkdir(parents=True, exist_ok=True)
    with DASHBOARD_STATUS.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=row)
        writer.writeheader()
        writer.writerow(row)
    print(f"{DASHBOARD_STATUS}: {invocation_state}; {len(actions)} actions; "
          f"{len(assertion_actions)} assertions; {len(problem_actions)} problem actions")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("grant-access", "sync", "run", "status", "dashboard-status"))
    args = parser.parse_args()
    if args.action == "grant-access":
        grant_dataset_access()
    elif args.action == "sync":
        provision_and_sync()
    elif args.action == "run":
        run()
    elif args.action == "dashboard-status":
        dashboard_status()
    else:
        status()


if __name__ == "__main__":
    main()
