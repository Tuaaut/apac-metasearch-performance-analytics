"""Export the two verified BigQuery Gold marts as Power BI Desktop CSV snapshots."""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
from pathlib import Path


PROJECT = "bq-dataform-sg"
LOCATION = "asia-southeast1"
ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "snapshot"
TABLES = {
    "gold_campaign_daily": (930, "date, market, channel, campaign_id, device_type"),
    "gold_incrementality_experiment": (15, "experiment_id"),
}


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


if __name__ == "__main__":
    main()
