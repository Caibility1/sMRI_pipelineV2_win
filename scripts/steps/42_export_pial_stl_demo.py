#!/usr/bin/env python3
"""Export FreeSurfer pial surfaces to STL files for 3D-print preparation."""

import argparse
import csv
import subprocess
import sys
from pathlib import Path


STL_NAMES = ("lh.pial.stl", "rh.pial.stl", "brain.pial.stl")


def nonempty(path):
    return path.is_file() and path.stat().st_size > 0


def stl_done(output_dir):
    return all(nonempty(output_dir / name) for name in STL_NAMES)


def discover_subject_dirs(recon_root, input_root, requested_subjects):
    if requested_subjects:
        return [recon_root / subject for subject in requested_subjects]
    return [
        recon_root / path.name
        for path in sorted(
            (item for item in input_root.iterdir() if item.is_dir()), key=lambda p: p.name
        )
    ]


def build_commands(subject_dir, output_dir, executable="mris_convert"):
    surf = subject_dir / "surf"
    return [
        [executable, str(surf / "lh.pial"), str(output_dir / "lh.pial.stl")],
        [executable, str(surf / "rh.pial"), str(output_dir / "rh.pial.stl")],
        [
            executable,
            "--combinesurfs",
            str(surf / "lh.pial"),
            str(surf / "rh.pial"),
            str(output_dir / "brain.pial.stl"),
        ],
    ]


def export_subject(subject_dir, output_dir, log_path, executable="mris_convert", force=False):
    required = [subject_dir / "surf" / "lh.pial", subject_dir / "surf" / "rh.pial"]
    missing = [str(path) for path in required if not nonempty(path)]
    if missing:
        raise FileNotFoundError("missing recon surfaces: " + ", ".join(missing))
    if stl_done(output_dir) and not force:
        return "checkpoint_exists"

    output_dir.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        for command in build_commands(subject_dir, output_dir, executable):
            message = "RUN: " + " ".join(command)
            print(message, flush=True)
            log.write(message + "\n")
            log.flush()
            subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
    if not stl_done(output_dir):
        raise RuntimeError("mris_convert returned successfully but one or more STL files are missing")
    return "exported"


def write_summary(path, rows):
    fields = ["subject", "status", "action", "error", "left_stl", "right_stl", "combined_stl"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Export recon-all pial surfaces as STL files.")
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--subject", action="append", default=[])
    parser.add_argument("--mris-convert", default="mris_convert")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    batch_dir = Path(args.batch_dir).expanduser().resolve()
    recon_root = batch_dir / "3_recon"
    stl_root = batch_dir / "4_stl"
    input_root = batch_dir / "1_T2toT1" / "data"
    if not recon_root.is_dir():
        print(f"Missing recon directory: {recon_root}", file=sys.stderr)
        return 2
    if not args.subject and not input_root.is_dir():
        print(f"Missing input directory: {input_root}", file=sys.stderr)
        return 2

    subject_dirs = discover_subject_dirs(recon_root, input_root, args.subject)
    rows = []
    failures = 0
    for subject_dir in subject_dirs:
        subject = subject_dir.name
        output_dir = stl_root / subject
        row = {
            "subject": subject,
            "status": "complete",
            "action": "",
            "error": "",
            "left_stl": str(output_dir / "lh.pial.stl"),
            "right_stl": str(output_dir / "rh.pial.stl"),
            "combined_stl": str(output_dir / "brain.pial.stl"),
        }
        try:
            row["action"] = export_subject(
                subject_dir,
                output_dir,
                batch_dir / "logs" / "stl" / f"{subject}.log",
                args.mris_convert,
                args.force,
            )
            print(f"[{subject}] STL export complete ({row['action']})", flush=True)
        except Exception as exc:
            failures += 1
            row["status"] = "failed"
            row["error"] = str(exc)
            print(f"[{subject}] FAILED: {exc}", file=sys.stderr, flush=True)
        rows.append(row)

    summary = batch_dir / "manifests" / "40_stl_summary.csv"
    write_summary(summary, rows)
    print(f"STL stage complete: {len(rows) - failures} succeeded, {failures} failed")
    print(f"Summary: {summary}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
