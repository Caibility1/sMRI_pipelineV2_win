#!/usr/bin/env python3
"""Prepare presurf inputs from segmentation outputs."""

import argparse
import csv
import shutil
from pathlib import Path

import numpy as np
import SimpleITK as sitk


def get_aseg(t1_nii, tissue, dk):
    aseg = np.zeros_like(dk, dtype=np.uint16)
    gm_mask = tissue == 2

    aseg[dk == 91] = 2
    aseg[dk == 92] = 41
    for i in range(1, 91, 2):
        aseg[(dk == i) & gm_mask] = 3
        aseg[(dk == (i + 1)) & gm_mask] = 42

    aseg[dk == 95] = 7
    aseg[dk == 96] = 46
    aseg[dk == 93] = 8
    aseg[dk == 94] = 47
    aseg[dk == 99] = 16

    aseg[dk == 55] = 4
    aseg[dk == 57] = 5
    aseg[dk == 56] = 43
    aseg[dk == 58] = 44
    aseg[dk == 97] = 14
    aseg[dk == 98] = 15
    aseg[dk == 53] = 31
    aseg[dk == 54] = 63

    aseg[dk == 41] = 11
    aseg[dk == 42] = 50
    aseg[dk == 43] = 12
    aseg[dk == 44] = 51
    aseg[dk == 45] = 13
    aseg[dk == 46] = 52
    aseg[dk == 47] = 10
    aseg[dk == 48] = 49
    aseg[dk == 49] = 26
    aseg[dk == 50] = 58
    aseg[dk == 51] = 28
    aseg[dk == 52] = 60
    aseg[dk == 35] = 17
    aseg[dk == 36] = 53
    aseg[dk == 39] = 18
    aseg[dk == 40] = 54

    aseg[dk == 106] = 251
    aseg[dk == 105] = 252
    aseg[dk == 104] = 253
    aseg[dk == 103] = 254
    aseg[dk == 102] = 255

    aseg_nii = sitk.GetImageFromArray(aseg)
    aseg_nii.SetDirection(t1_nii.GetDirection())
    aseg_nii.SetOrigin(t1_nii.GetOrigin())
    aseg_nii.SetSpacing(t1_nii.GetSpacing())
    return aseg_nii


def nonempty_file(path):
    return path.is_file() and path.stat().st_size > 0


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "subject_name",
        "status",
        "error",
        "source_dir",
        "target_dir",
        "masked",
        "aseg",
        "mprage",
        "brain_size",
        "dk_size",
        "tissue_size",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def process_subject(source_subdir, target_root):
    target_subdir = target_root / source_subdir.name
    brain_path = source_subdir / "brain.nii.gz"
    dk_path = source_subdir / "dk-struct.nii.gz"
    tissue_path = source_subdir / "tissue.nii.gz"
    row = {
        "subject_name": source_subdir.name,
        "status": "",
        "error": "",
        "source_dir": str(source_subdir),
        "target_dir": str(target_subdir),
        "masked": str(target_subdir / "masked.nii.gz"),
        "aseg": str(target_subdir / "aseg.nii.gz"),
        "mprage": str(target_subdir / "mprage.nii.gz"),
        "brain_size": "",
        "dk_size": "",
        "tissue_size": "",
    }
    if all(nonempty_file(target_subdir / name) for name in ["masked.nii.gz", "aseg.nii.gz", "mprage.nii.gz"]):
        row["status"] = "skipped"
        return row
    missing = [path.name for path in [brain_path, dk_path, tissue_path] if not nonempty_file(path)]
    if missing:
        row["status"] = "failed"
        row["error"] = "missing " + ",".join(missing)
        return row
    try:
        brain_nii = sitk.ReadImage(str(brain_path))
        dk_nii = sitk.ReadImage(str(dk_path))
        tissue_nii = sitk.ReadImage(str(tissue_path))
        row["brain_size"] = "x".join(str(x) for x in brain_nii.GetSize())
        row["dk_size"] = "x".join(str(x) for x in dk_nii.GetSize())
        row["tissue_size"] = "x".join(str(x) for x in tissue_nii.GetSize())
        if (brain_nii.GetSize() != dk_nii.GetSize()) or (brain_nii.GetSize() != tissue_nii.GetSize()):
            row["status"] = "failed"
            row["error"] = f"size mismatch brain={brain_nii.GetSize()} dk={dk_nii.GetSize()} tissue={tissue_nii.GetSize()}"
            return row
        tissue = sitk.GetArrayFromImage(tissue_nii)
        dk = sitk.GetArrayFromImage(dk_nii)
        aseg_nii = get_aseg(brain_nii, tissue, dk)
        target_subdir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(brain_path, target_subdir / "masked.nii.gz")
        sitk.WriteImage(aseg_nii, str(target_subdir / "aseg.nii.gz"))
        shutil.copy2(brain_path, target_subdir / "mprage.nii.gz")
        row["status"] = "success"
    except Exception as exc:
        row["status"] = "failed"
        row["error"] = str(exc)
    return row


def process(source_dir, target_root):
    return [
        process_subject(source_subdir, target_root)
        for source_subdir in sorted([p for p in source_dir.iterdir() if p.is_dir()], key=lambda p: p.name)
    ]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--source-dir")
    parser.add_argument("--target-root")
    parser.add_argument("--summary-name", default="30_presurf_summary.csv")
    args = parser.parse_args(argv)
    batch_dir = Path(args.batch_dir).resolve()
    source_dir = Path(args.source_dir).resolve() if args.source_dir else batch_dir / "6_seg"
    target_root = Path(args.target_root).resolve() if args.target_root else batch_dir / "7_presurf"
    if not source_dir.is_dir():
        print(f"Missing segmentation directory: {source_dir}")
        return 2
    rows = process(source_dir, target_root)
    summary = batch_dir / "manifests" / args.summary_name
    write_csv(summary, rows)
    print(f"Wrote {summary}")
    return 1 if any(row["status"] == "failed" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
