"""Export the two verified BigQuery Gold marts as Power BI Desktop CSV snapshots."""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


PROJECT = "bq-dataform-sg"
LOCATION = "asia-southeast1"
ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "snapshot"
TABLES = {
    "gold_campaign_daily": (930, "date, market, channel, campaign_id, device_type"),
    "gold_incrementality_experiment": (15, "experiment_id"),
}
METADATA_FIELDS = (
    "data_through_date", "snapshot_exported_utc", "dataform_workflow_state",
    "dataform_completed_utc", "dataform_total_actions", "dataform_problem_actions",
    "dataform_assertion_actions", "dataform_problem_assertions", "powerbi_import_instruction",
)


def as_utc_naive(value: str) -> str:
    if not value:
        return ""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).replace(
        tzinfo=None).isoformat(timespec="seconds")


def write_refresh_metadata() -> None:
    campaign_path = SNAPSHOT / "gold_campaign_daily.csv"
    with campaign_path.open(newline="", encoding="utf-8") as file:
        data_through_date = max(row["date"] for row in csv.DictReader(file))
    status_path = SNAPSHOT / "dataform_workflow_status.csv"
    workflow = {}
    if status_path.exists():
        with status_path.open(newline="", encoding="utf-8") as file:
            workflow = next(csv.DictReader(file), {})
    row = {
        "data_through_date": data_through_date,
        "snapshot_exported_utc": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds"),
        "dataform_workflow_state": workflow.get("invocation_state", "UNKNOWN"),
        "dataform_completed_utc": as_utc_naive(workflow.get("workflow_end_utc", "")),
        "dataform_total_actions": workflow.get("total_actions", ""),
        "dataform_problem_actions": workflow.get("problem_actions", ""),
        "dataform_assertion_actions": workflow.get("assertion_actions", ""),
        "dataform_problem_assertions": workflow.get("problem_assertion_actions", ""),
        "powerbi_import_instruction": "Open the PBIP and select Home > Refresh to load this snapshot.",
    }
    metadata_path = SNAPSHOT / "refresh_metadata.csv"
    with metadata_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=METADATA_FIELDS)
        writer.writeheader()
        writer.writerow(row)
    print(f"{metadata_path.name}: exported {row['snapshot_exported_utc']} UTC")


def main() -> None:
    bq = shutil.which("bq.cmd" if os.name == "nt" else "bq")
    if not bq:
        raise RuntimeError("BigQuery CLI not found on PATH")
    SNAPSHOT.mkdir(parents=True, exist_ok=True)
    for table, (expected, order) in TABLES.items():
        query = f"SELECT * FROM `{PROJECT}.apac_meta_gold.{table}` ORDER BY {order}"
        command = [
            bq, "query", f"--project_id={PROJECT}", f"--location={LOCATION}",
            "--use_legacy_sql=false", "--format=csv", "--max_rows=100000",
            "--quiet", query,
        ]
        result = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")
        path = SNAPSHOT / f"{table}.csv"
        path.write_text(result.stdout, encoding="utf-8", newline="")
        with path.open(newline="", encoding="utf-8") as f:
            count = sum(1 for _ in csv.DictReader(f))
        if count != expected:
            path.unlink()
            raise RuntimeError(f"{table}: exported {count} rows; expected {expected}")
        print(f"{path.name}: {count:,} rows")
    write_refresh_metadata()


if __name__ == "__main__":
    main()
