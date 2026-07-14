#!/usr/bin/env python3
"""Check expected nnU-Net masks from nnunet_id_map.csv."""

import argparse
import csv
from pathlib import Path


def read_map(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["subject_name", "nnunet_case_id", "expected_mask", "status", "error"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def collect(batch_dir):
    map_path = batch_dir / "2_nnunet_input" / "nnunet_id_map.csv"
    rows = []
    for row in read_map(map_path):
        mask = Path(row["expected_mask"])
        ok = mask.is_file() and mask.stat().st_size > 0
        rows.append({
            "subject_name": row["subject_name"],
            "nnunet_case_id": row["nnunet_case_id"],
            "expected_mask": str(mask),
            "status": "success" if ok else "failed",
            "error": "" if ok else "missing expected mask",
        })
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--require-all", action="store_true")
    args = parser.parse_args(argv)
    batch_dir = Path(args.batch_dir).resolve()
    rows = collect(batch_dir)
    path = batch_dir / "manifests" / "05_nnunet_output_summary.csv"
    write_csv(path, rows)
    print(f"Wrote {path}")
    if args.require_all and (not rows or any(row["status"] != "success" for row in rows)):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
