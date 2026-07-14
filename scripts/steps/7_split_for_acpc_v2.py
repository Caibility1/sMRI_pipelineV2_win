#!/usr/bin/env python3
"""Split 3_skullstrip outputs into 4_results branches for ACPC."""

import argparse
import csv
import shutil
from pathlib import Path


SUMMARY_NAME = "10_split_for_acpc_summary.csv"


def nonempty_file(path):
    return path.is_file() and path.stat().st_size > 0


def existing_empty_file(path):
    return path.is_file() and path.stat().st_size == 0


def copy_subject(src_dir, dst_dir, required_names):
    created = not dst_dir.exists()
    if created:
        dst_dir.mkdir(parents=True, exist_ok=False)
    copied = []
    for name in required_names:
        src = src_dir / name
        dst = dst_dir / name
        if not nonempty_file(src):
            return "failed", f"missing or empty source {name}"
        if existing_empty_file(dst):
            return "failed", f"zero-size existing target {dst}"
        if dst.exists():
            continue
        shutil.copy2(src, dst)
        copied.append(name)
    if created:
        return "copied", ""
    if copied:
        return "repaired", "copied missing files: " + ",".join(copied)
    return "skipped_complete", ""


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["subject_name", "branch", "status", "error", "source_dir", "target_dir"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def process(batch_dir):
    src_root = batch_dir / "3_skullstrip" / "data"
    results_root = batch_dir / "4_results"
    rows = []
    for src_dir in sorted([p for p in src_root.iterdir() if p.is_dir()], key=lambda p: p.name):
        has_t1 = nonempty_file(src_dir / "T1.nii.gz")
        has_mask = nonempty_file(src_dir / "mask.nii.gz")
        has_t2 = nonempty_file(src_dir / "T2.nii.gz")
        empty_t2 = existing_empty_file(src_dir / "T2.nii.gz")
        branch = "T1T2" if has_t2 else "justT1"
        dst_dir = results_root / branch / src_dir.name
        other_branch = "justT1" if branch == "T1T2" else "T1T2"
        other_dst = results_root / other_branch / src_dir.name
        row = {
            "subject_name": src_dir.name,
            "branch": branch,
            "status": "",
            "error": "",
            "source_dir": str(src_dir),
            "target_dir": str(dst_dir),
        }
        if not has_t1 or not has_mask:
            row["status"] = "failed"
            missing = []
            if not has_t1:
                missing.append("T1.nii.gz")
            if not has_mask:
                missing.append("mask.nii.gz")
            row["error"] = "missing " + ",".join(missing)
            rows.append(row)
            continue
        if empty_t2:
            row["status"] = "failed"
            row["error"] = "zero-size source T2.nii.gz"
            rows.append(row)
            continue
        if other_dst.exists():
            row["status"] = "failed"
            row["error"] = f"subject also exists in {other_branch}: {other_dst}"
            rows.append(row)
            continue
        try:
            required = ["T1.nii.gz", "mask.nii.gz"]
            if has_t2:
                required.append("T2.nii.gz")
            row["status"], row["error"] = copy_subject(src_dir, dst_dir, required)
        except Exception as exc:
            row["status"] = "failed"
            row["error"] = str(exc)
        rows.append(row)
    write_csv(batch_dir / "manifests" / SUMMARY_NAME, rows)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", required=True)
    args = parser.parse_args(argv)
    batch_dir = Path(args.batch_dir).resolve()
    src_root = batch_dir / "3_skullstrip" / "data"
    if not src_root.is_dir():
        print(f"Missing skullstrip data directory: {src_root}")
        return 2
    rows = process(batch_dir)
    path = batch_dir / "manifests" / SUMMARY_NAME
    print(f"Wrote {path}")
    return 1 if any(row["status"] == "failed" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
