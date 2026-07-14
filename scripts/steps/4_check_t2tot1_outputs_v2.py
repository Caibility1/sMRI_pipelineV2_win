#!/usr/bin/env python3
"""Write T2-to-T1 registration input/output summaries."""

import argparse
import csv
from pathlib import Path


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["subject", "has_t1", "has_t2", "registered", "status", "error"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def collect(batch_dir, input_only=False):
    rows = []
    data_dir = batch_dir / "1_T2toT1" / "data"
    for subject_dir in sorted([p for p in data_dir.iterdir() if p.is_dir()], key=lambda p: p.name):
        t1 = subject_dir / "T1.nii.gz"
        t2 = subject_dir / "T2.nii.gz"
        registered = subject_dir / "registration" / "T2_to_T1.nii.gz"
        has_t1 = t1.is_file() and t1.stat().st_size > 0
        has_t2 = t2.is_file() and t2.stat().st_size > 0
        is_registered = registered.is_file() and registered.stat().st_size > 0
        if not has_t1:
            status, error = "failed", "missing T1"
        elif not has_t2:
            status, error = "t1_only", ""
        elif is_registered:
            status, error = "success", ""
        elif input_only:
            status, error = "pending", ""
        else:
            status, error = "failed", "missing registration output"
        rows.append({
            "subject": subject_dir.name,
            "has_t1": "yes" if has_t1 else "no",
            "has_t2": "yes" if has_t2 else "no",
            "registered": "yes" if is_registered else "no",
            "status": status,
            "error": error,
        })
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--input", action="store_true")
    args = parser.parse_args(argv)
    batch_dir = Path(args.batch_dir).resolve()
    name = "02_t2tot1_input_summary.csv" if args.input else "03_t2tot1_output_summary.csv"
    rows = collect(batch_dir, input_only=args.input)
    write_csv(batch_dir / "manifests" / name, rows)
    print(f"Wrote {batch_dir / 'manifests' / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
