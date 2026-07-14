#!/usr/bin/env python3
"""Check ACPC preprocessing outputs under 4_results."""

import argparse
import csv
from pathlib import Path


SUMMARY_NAME = "11_acpc_summary.csv"


def nonempty_file(path):
    return path.is_file() and path.stat().st_size > 0


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "branch",
        "subject_name",
        "status",
        "error",
        "t1_acpc",
        "t2_acpc",
        "myelin_dir",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def collect_branch(batch_dir, branch):
    root = batch_dir / "4_results" / branch
    rows = []
    if not root.is_dir():
        return rows
    for subject_dir in sorted([p for p in root.iterdir() if p.is_dir() and p.name != "qc"], key=lambda p: p.name):
        t1 = subject_dir / "T1_acpc.nii.gz"
        t2 = subject_dir / "T2_acpc.nii.gz"
        myelin = subject_dir / "Myelin"
        missing = []
        if not nonempty_file(t1):
            missing.append("T1_acpc.nii.gz")
        if branch == "T1T2" and not nonempty_file(t2):
            missing.append("T2_acpc.nii.gz")
        status = "success" if not missing else "failed"
        rows.append({
            "branch": branch,
            "subject_name": subject_dir.name,
            "status": status,
            "error": "" if not missing else "missing " + ",".join(missing),
            "t1_acpc": str(t1),
            "t2_acpc": str(t2) if branch == "T1T2" else "",
            "myelin_dir": str(myelin) if myelin.is_dir() else "",
        })
    return rows


def collect(batch_dir, branch=None):
    branches = [branch] if branch else ["T1T2", "justT1"]
    rows = []
    for item in branches:
        rows.extend(collect_branch(batch_dir, item))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--branch", choices=["T1T2", "justT1"])
    parser.add_argument("--require-all", action="store_true")
    args = parser.parse_args(argv)
    batch_dir = Path(args.batch_dir).resolve()
    rows = collect(batch_dir, branch=args.branch)
    path = batch_dir / "manifests" / SUMMARY_NAME
    if args.branch:
        rows = [row for row in read_csv(path) if row.get("branch") != args.branch] + rows
    write_csv(path, rows)
    print(f"Wrote {path}")
    if args.require_all and (not rows or any(row["status"] != "success" for row in rows)):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
