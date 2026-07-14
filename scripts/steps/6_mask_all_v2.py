#!/usr/bin/env python3
"""Merge registration and nnU-Net masks into 3_skullstrip/data."""

import argparse
import csv
import shutil
import sys
from pathlib import Path


def shape_status(image_shape, mask_shape):
    return "ok" if tuple(image_shape) == tuple(mask_shape) else "shape_mismatch"


def read_map(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["subject_name", "status", "error", "has_t2", "t1_out", "t2_out", "mask_out"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def save_masked(src_img, mask_img, out_path):
    import nibabel as nib

    data = src_img.get_fdata() * mask_img.get_fdata()
    out = nib.Nifti1Image(data, src_img.affine, src_img.header)
    nib.save(out, out_path)


def process_subject(batch_dir, map_row):
    import nibabel as nib

    subject = map_row["subject_name"]
    subject_dir = batch_dir / "1_T2toT1" / "data" / subject
    out_dir = batch_dir / "3_skullstrip" / "data" / subject
    t1_path = subject_dir / "T1.nii.gz"
    t2_reg_path = subject_dir / "registration" / "T2_to_T1.nii.gz"
    mask_path = Path(map_row["expected_mask"])
    row = {
        "subject_name": subject,
        "status": "",
        "error": "",
        "has_t2": "yes" if t2_reg_path.is_file() else "no",
        "t1_out": str(out_dir / "T1.nii.gz"),
        "t2_out": str(out_dir / "T2.nii.gz"),
        "mask_out": str(out_dir / "mask.nii.gz"),
    }
    if not t1_path.is_file():
        row["status"] = "failed"
        row["error"] = "missing T1"
        return row
    if not mask_path.is_file():
        row["status"] = "failed"
        row["error"] = "missing mask"
        return row
    out_t1 = out_dir / "T1.nii.gz"
    out_mask = out_dir / "mask.nii.gz"
    out_t2 = out_dir / "T2.nii.gz"
    if out_t1.is_file() and out_mask.is_file() and (not t2_reg_path.is_file() or out_t2.is_file()):
        row["status"] = "skipped"
        return row
    t1_img = nib.load(str(t1_path))
    mask_img = nib.load(str(mask_path))
    if shape_status(t1_img.shape, mask_img.shape) != "ok":
        row["status"] = "failed"
        row["error"] = f"T1/mask shape mismatch: {t1_img.shape} vs {mask_img.shape}"
        return row
    out_dir.mkdir(parents=True, exist_ok=True)
    save_masked(t1_img, mask_img, out_t1)
    shutil.copy2(mask_path, out_mask)
    if t2_reg_path.is_file() and t2_reg_path.stat().st_size > 0:
        t2_img = nib.load(str(t2_reg_path))
        if shape_status(t2_img.shape, mask_img.shape) != "ok":
            row["status"] = "warning"
            row["error"] = f"T2/mask shape mismatch: {t2_img.shape} vs {mask_img.shape}"
            return row
        save_masked(t2_img, mask_img, out_t2)
        row["has_t2"] = "yes"
    else:
        row["has_t2"] = "no"
    row["status"] = "success"
    return row


def process(batch_dir):
    map_path = batch_dir / "2_nnunet_input" / "nnunet_id_map.csv"
    rows = []
    for map_row in read_map(map_path):
        rows.append(process_subject(batch_dir, map_row))
    summary = batch_dir / "manifests" / "06_mask_all_summary.csv"
    write_csv(summary, rows)
    return rows


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", required=True)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    batch_dir = Path(args.batch_dir).resolve()
    try:
        rows = process(batch_dir)
    except ImportError as exc:
        print("Missing nibabel/numpy. Install or activate the sMRI_pipeline_win environment.", file=sys.stderr)
        raise SystemExit(2) from exc
    failed = [r for r in rows if r["status"] == "failed"]
    print(f"Wrote {batch_dir / 'manifests' / '06_mask_all_summary.csv'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

