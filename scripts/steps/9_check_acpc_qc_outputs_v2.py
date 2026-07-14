#!/usr/bin/env python3
"""Check ACPC QC PNG outputs."""

import argparse
import csv
from pathlib import Path


SUMMARY_NAME = "12_acpc_qc_summary.csv"


def base_subject_name(subject_name):
    import re

    return re.sub(r"_[0-9]{1,3}mo$", "", subject_name)


def nonempty_file(path):
    return path.is_file() and path.stat().st_size > 0


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["branch", "subject_name", "status", "error", "qc_png"]
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
    qc_dir = root / "qc"
    rows = []
    if not root.is_dir():
        return rows
    for subject_dir in sorted([p for p in root.iterdir() if p.is_dir() and p.name != "qc"], key=lambda p: p.name):
        png = qc_dir / f"{base_subject_name(subject_dir.name)}.png"
        ok = nonempty_file(png)
        rows.append({
            "branch": branch,
            "subject_name": subject_dir.name,
            "status": "success" if ok else "failed",
            "error": "" if ok else "missing qc png",
            "qc_png": str(png),
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
    args = parser.parse_args(argv)
    batch_dir = Path(args.batch_dir).resolve()
    rows = collect(batch_dir, branch=args.branch)
    path = batch_dir / "manifests" / SUMMARY_NAME
    if args.branch:
        rows = [row for row in read_csv(path) if row.get("branch") != args.branch] + rows
    write_csv(path, rows)
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
