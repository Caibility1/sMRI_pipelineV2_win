#!/usr/bin/env python3
"""Prepare nnU-Net Task523 inference inputs and mapping files."""

import argparse
import csv
import json
import re
import shutil
import sys
from pathlib import Path


SUMMARY_NAME = "04_nnunet_input_summary.csv"
MAP_NAME = "nnunet_id_map.csv"


def parse_subject(subject_name):
    match = re.match(r"^(?P<subject_id>.+)_(?P<age_month>\d{1,3})mo$", subject_name, re.IGNORECASE)
    if not match:
        return subject_name, ""
    return match.group("subject_id"), match.group("age_month")


def make_case_id(subject_name):
    compact = re.sub(r"[^A-Za-z0-9]", "", subject_name)
    return f"T523_{compact}"


def make_input_name(case_id):
    return f"{case_id}_0000.nii.gz"


def build_dataset_json(input_names):
    return {
        "description": "",
        "labels": {"0": "background", "1": "Brain"},
        "licence": "hands off!",
        "modality": {"0": "T1"},
        "name": "T523",
        "numTest": len(input_names),
        "numTraining": 0,
        "reference": "",
        "release": "0.0",
        "tensorImageSize": "4D",
        "test": [f"./imagesTs/{name}" for name in sorted(input_names)],
    }


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def process(batch_dir, overwrite=False, dry_run=False):
    data_dir = batch_dir / "1_T2toT1" / "data"
    input_root = batch_dir / "2_nnunet_input"
    images_dir = input_root / "imagesTs"
    output_dir = batch_dir / "2_nnunet_output"
    images_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    input_names = []
    failures = 0
    seen_cases = {}
    for subject_dir in sorted([p for p in data_dir.iterdir() if p.is_dir()], key=lambda p: p.name):
        t1 = subject_dir / "T1.nii.gz"
        subject_id, age_month = parse_subject(subject_dir.name)
        case_id = make_case_id(subject_dir.name)
        input_name = make_input_name(case_id)
        target = images_dir / input_name
        expected_mask = output_dir / f"{case_id}.nii.gz"
        row = {
            "subject_name": subject_dir.name,
            "subject_id": subject_id,
            "age_month": age_month,
            "nnunet_case_id": case_id,
            "nnunet_input": str(target),
            "expected_mask": str(expected_mask),
            "status": "",
            "error": "",
        }
        if case_id in seen_cases:
            row["status"] = "failed"
            row["error"] = f"duplicate case id also used by {seen_cases[case_id]}"
            failures += 1
            rows.append(row)
            continue
        seen_cases[case_id] = subject_dir.name
        if not t1.is_file():
            row["status"] = "failed"
            row["error"] = "missing T1.nii.gz"
            failures += 1
            rows.append(row)
            continue
        if expected_mask.is_file() and expected_mask.stat().st_size > 0:
            row["status"] = "skipped_mask_exists"
        elif target.exists() and not overwrite:
            row["status"] = "skipped_input_exists"
        elif dry_run:
            row["status"] = "would_copy"
        else:
            shutil.copy2(t1, target)
            row["status"] = "copied"
        input_names.append(input_name)
        rows.append(row)
    dataset = build_dataset_json(input_names)
    (input_root / "dataset.json").write_text(json.dumps(dataset, indent=4), encoding="utf-8")
    fields = [
        "subject_name",
        "subject_id",
        "age_month",
        "nnunet_case_id",
        "nnunet_input",
        "expected_mask",
        "status",
        "error",
    ]
    write_csv(input_root / MAP_NAME, rows, fields)
    write_csv(batch_dir / "manifests" / SUMMARY_NAME, rows, fields)
    return failures


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    batch_dir = Path(args.batch_dir).resolve()
    data_dir = batch_dir / "1_T2toT1" / "data"
    if not data_dir.is_dir():
        print(f"Missing data directory: {data_dir}", file=sys.stderr)
        return 2
    failures = process(batch_dir, overwrite=args.overwrite, dry_run=args.dry_run)
    print(f"Wrote {batch_dir / '2_nnunet_input' / MAP_NAME}")
    if failures:
        print(f"nnUNet input failures: {failures}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
