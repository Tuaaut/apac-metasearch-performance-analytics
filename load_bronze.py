"""Validate local CSVs and replace dedicated BigQuery Bronze tables."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from generate_data import FIELDS, ROOT, read_csv, validate


RETIRED_BRONZE_TABLES = ("incrementality_experiment",)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="bq-dataform-sg")
    parser.add_argument("--dataset", default="apac_meta_bronze")
    parser.add_argument("--location", default="asia-southeast1")
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument(
        "--table",
        choices=tuple(FIELDS),
        help="Load and verify one Bronze table. Omit to load every active table.",
    )
    args = parser.parse_args()
    validate(args.data)
    bq = shutil.which("bq.cmd" if os.name == "nt" else "bq")
    if not bq:
        parser.error("BigQuery CLI was not found on PATH")
    tables = {args.table: FIELDS[args.table]} if args.table else FIELDS
    for name, fields in tables.items():
        target = f"{args.project}:{args.dataset}.{name}"
        source = str((args.data / f"{name}.csv").resolve())
        schema = ",".join(f"{field}:STRING" for field in fields)
        command = [
            bq, "load", "--replace", "--source_format=CSV",
            "--skip_leading_rows=1", f"--location={args.location}",
            target, source, schema,
        ]
        print(f"Loading {target}...")
        subprocess.run(command, check=True)
        metadata = subprocess.run(
            [bq, "show", "--format=prettyjson", target],
            check=True, capture_output=True, text=True,
        )
        actual = int(json.loads(metadata.stdout)["numRows"])
        expected = len(read_csv(args.data, name))
        if actual != expected:
            raise RuntimeError(f"{target}: loaded {actual} rows; expected {expected}")
        print(f"Verified {actual:,} rows in {target}")
    for name in RETIRED_BRONZE_TABLES if not args.table else ():
        target = f"{args.project}:{args.dataset}.{name}"
        exists = subprocess.run(
            [bq, "show", target], capture_output=True, text=True
        ).returncode == 0
        if exists:
            subprocess.run([bq, "rm", "-f", "-t", target], check=True)
            print(f"Removed retired Bronze table {target}")
    print("Bronze load complete.")


if __name__ == "__main__":
    main()
