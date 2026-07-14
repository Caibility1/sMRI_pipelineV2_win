#!/usr/bin/env python3
"""Summarize infant_recon_all outputs under a presurf/recon root."""

import argparse
import csv
import re
from pathlib import Path


def nonempty_file(path):
    return path.is_file() and path.stat().st_size > 0


def recon_started(subject_dir):
    return any((subject_dir / name).exists() for name in ["scripts", "mri", "surf", "label", "stats"])


def recon_failure(subject_dir):
    log_path = subject_dir / "log" / "recon.log"
    if not log_path.is_file():
        return ""
    text = log_path.read_text(encoding="utf-8", errors="replace")
    failure_patterns = [
        "ERROR | Fatal",
        "infant_recon_all failed",
        "failed with exit code",
        "error while loading shared libraries",
    ]
    for pattern in failure_patterns:
        if pattern in text:
            return pattern
    return ""


def recon_done(subject_dir):
    done_markers = [
        subject_dir / "scripts" / "recon-all.done",
        subject_dir / "surf" / "lh.white",
        subject_dir / "surf" / "rh.white",
        subject_dir / "stats" / "aseg.stats",
    ]
    return any(path.exists() for path in done_markers)


def parse_age(subject_name):
    match = re.search(r"_(\d{1,3})mo$", subject_name)
    return match.group(1) if match else ""


def collect(root):
    rows = []
    if not root.is_dir():
        return rows
    for subject_dir in sorted([p for p in root.iterdir() if p.is_dir() and p.name != "logs"], key=lambda p: p.name):
        missing = []
        for name in ["masked.nii.gz", "aseg.nii.gz"]:
            if not nonempty_file(subject_dir / name):
                missing.append(name)
        if missing:
            status = "failed"
            error = "missing " + ",".join(missing)
        else:
            if recon_done(subject_dir):
                status = "success"
                error = ""
            else:
                failure = recon_failure(subject_dir)
                if failure:
                    status = "failed"
                    error = f"recon log indicates failure: {failure}"
                elif recon_started(subject_dir):
                    status = "warning"
                    error = "recon outputs exist but no known done marker"
                else:
                    status = "pending"
                    error = ""
        rows.append({
            "subject_name": subject_dir.name,
            "age_month": parse_age(subject_dir.name),
            "status": status,
            "error": error,
            "subject_dir": str(subject_dir),
            "masked": str(subject_dir / "masked.nii.gz"),
            "aseg": str(subject_dir / "aseg.nii.gz"),
        })
    return rows


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["subject_name", "age_month", "status", "error", "subject_dir", "masked", "aseg"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--target-root")
    parser.add_argument("--summary-name", default="40_recon_summary.csv")
    args = parser.parse_args(argv)
    batch_dir = Path(args.batch_dir).resolve()
    target_root = Path(args.target_root).resolve() if args.target_root else batch_dir / "7_presurf"
    rows = collect(target_root)
    summary = batch_dir / "manifests" / args.summary_name
    write_csv(summary, rows)
    print(f"Wrote {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



