#!/usr/bin/env python3
"""Standardize each intake subject folder to T1.nii.gz and optional T2.nii.gz."""

import argparse
import csv
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace


SUMMARY_NAME = "01_copy_rename_summary.csv"


def is_nifti_gz(path):
    return path.is_file() and path.name.lower().endswith(".nii.gz")


def modality_candidates(subject_dir, modality):
    prefix = modality.lower()
    target_name = f"{modality.upper()}.nii.gz"
    out = []
    for path in subject_dir.iterdir():
        if not is_nifti_gz(path):
            continue
        name = path.name
        lower = name.lower()
        if name == target_name or lower.startswith(prefix):
            out.append(path)
    return sorted(out, key=lambda p: p.name.lower())


def inspect_subject(subject_dir):
    t1 = modality_candidates(subject_dir, "T1")
    t2 = modality_candidates(subject_dir, "T2")
    if len(t1) == 0:
        return SimpleNamespace(status="failed", error="missing T1", t1=t1, t2=t2)
    if len(t1) > 1:
        return SimpleNamespace(status="failed", error="multiple T1 candidates", t1=t1, t2=t2)
    if len(t2) > 1:
        return SimpleNamespace(status="failed", error="multiple T2 candidates", t1=t1, t2=t2)
    status = "success" if t2 else "t1_only"
    return SimpleNamespace(status=status, error="", t1=t1, t2=t2)


def rename_one(src, dst, dry_run=False):
    if src.resolve() == dst.resolve():
        return "skipped"
    if dst.exists():
        raise FileExistsError(f"target exists: {dst}")
    if not dry_run:
        src.rename(dst)
    return "renamed"


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "subject",
        "status",
        "error",
        "has_t2",
        "t1_source",
        "t1_target",
        "t1_action",
        "t2_source",
        "t2_target",
        "t2_action",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def process(data_dir, summary_path, dry_run=False):
    rows = []
    strict_failures = 0
    for subject_dir in sorted([p for p in data_dir.iterdir() if p.is_dir()], key=lambda p: p.name):
        result = inspect_subject(subject_dir)
        row = {
            "subject": subject_dir.name,
            "status": result.status,
            "error": result.error,
            "has_t2": "yes" if result.t2 else "no",
            "t1_source": str(result.t1[0]) if result.t1 else "",
            "t1_target": str(subject_dir / "T1.nii.gz"),
            "t1_action": "",
            "t2_source": str(result.t2[0]) if result.t2 else "",
            "t2_target": str(subject_dir / "T2.nii.gz") if result.t2 else "",
            "t2_action": "",
        }
        if result.status == "failed":
            strict_failures += 1
            rows.append(row)
            continue
        try:
            row["t1_action"] = rename_one(result.t1[0], subject_dir / "T1.nii.gz", dry_run=dry_run)
            if result.t2:
                row["t2_action"] = rename_one(result.t2[0], subject_dir / "T2.nii.gz", dry_run=dry_run)
        except Exception as exc:
            row["status"] = "failed"
            row["error"] = str(exc)
            strict_failures += 1
        rows.append(row)
    write_csv(summary_path, rows)
    return strict_failures


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    batch_dir = Path(args.batch_dir).resolve()
    data_dir = batch_dir / "1_T2toT1" / "data"
    if not data_dir.is_dir():
        print(f"Missing intake data directory: {data_dir}", file=sys.stderr)
        return 2
    summary = batch_dir / "manifests" / SUMMARY_NAME
    failures = process(data_dir, summary, dry_run=args.dry_run)
    print(f"Wrote {summary}")
    if failures:
        print(f"Strict intake failures: {failures}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
