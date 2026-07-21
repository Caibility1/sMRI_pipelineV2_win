#!/usr/bin/env python3
"""Summarize standard FreeSurfer recon-all outputs for the teaching pipeline."""

import argparse
import csv
from pathlib import Path


REQUIRED_OUTPUTS = (
    "scripts/recon-all.done",
    "surf/lh.pial",
    "surf/rh.pial",
    "mri/brainmask.mgz",
    "mri/aseg.mgz",
)


def nonempty(path):
    return path.is_file() and path.stat().st_size > 0


def recon_done(subject_dir):
    return all(nonempty(subject_dir / relative) for relative in REQUIRED_OUTPUTS)


def failure_message(subject_dir):
    error_marker = subject_dir / "scripts" / "recon-all.error"
    if error_marker.is_file():
        return "recon-all.error exists"
    log_path = subject_dir / "scripts" / "recon-all.log"
    if not log_path.is_file():
        return ""
    text = log_path.read_text(encoding="utf-8", errors="replace")[-200000:]
    for marker in ("recon-all -s", "exited with ERRORS", "ERROR:"):
        if marker in text and marker != "recon-all -s":
            return marker
    return ""


def collect(recon_root, input_root):
    rows = []
    subjects = sorted((path for path in input_root.iterdir() if path.is_dir()), key=lambda p: p.name)
    for input_dir in subjects:
        subject_dir = recon_root / input_dir.name
        missing = [relative for relative in REQUIRED_OUTPUTS if not nonempty(subject_dir / relative)]
        failure = failure_message(subject_dir)
        if recon_done(subject_dir):
            status = "success"
            error = ""
        elif failure:
            status = "failed"
            error = failure
        elif subject_dir.exists():
            status = "partial"
            error = "missing " + ",".join(missing)
        else:
            status = "pending"
            error = ""
        rows.append(
            {
                "subject": input_dir.name,
                "status": status,
                "error": error,
                "has_t2": "yes" if nonempty(input_dir / "T2.nii.gz") else "no",
                "subject_dir": str(subject_dir),
                "brainmask": str(subject_dir / "mri" / "brainmask.mgz"),
                "lh_pial": str(subject_dir / "surf" / "lh.pial"),
                "rh_pial": str(subject_dir / "surf" / "rh.pial"),
            }
        )
    return rows


def write_csv(path, rows):
    fields = ["subject", "status", "error", "has_t2", "subject_dir", "brainmask", "lh_pial", "rh_pial"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check standard FreeSurfer recon-all outputs.")
    parser.add_argument("--batch-dir", required=True)
    args = parser.parse_args(argv)
    batch_dir = Path(args.batch_dir).expanduser().resolve()
    input_root = batch_dir / "1_T2toT1" / "data"
    recon_root = batch_dir / "3_recon"
    if not input_root.is_dir():
        parser.error(f"missing input directory: {input_root}")
    rows = collect(recon_root, input_root)
    summary = batch_dir / "manifests" / "30_recon_summary.csv"
    write_csv(summary, rows)
    success = sum(row["status"] == "success" for row in rows)
    failed = sum(row["status"] == "failed" for row in rows)
    partial = sum(row["status"] == "partial" for row in rows)
    print(f"Recon check complete: {success} complete, {failed} failed, {partial} partial")
    print(f"Summary: {summary}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
