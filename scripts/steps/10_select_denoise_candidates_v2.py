#!/usr/bin/env python3
"""Copy Fail/Questionable ACPC outputs into flat 5_questionable denoise folders."""

import argparse
import csv
from decimal import Decimal, InvalidOperation
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import nibabel as nib
import numpy as np


SUMMARY_NAME = "20_questionable_summary.csv"
MOARDIFF_INPUT_SHAPE = (192, 240, 192)


AGE_SUFFIX_RE = re.compile(r"^(?P<subject_id>.+)_(?P<age_month>\d{1,3})mo$", re.IGNORECASE)


def parse_age_suffix(name):
    match = AGE_SUFFIX_RE.match(str(name).strip())
    if not match:
        return str(name).strip(), ""
    return match.group("subject_id"), match.group("age_month")



def normalize_numeric_id_text(text):
    compact = re.sub(r"[\s,]+", "", str(text).strip())
    if re.fullmatch(r"[+-]?\d+(?:\.0+)?", compact):
        return compact.split(".", 1)[0]
    if re.fullmatch(r"[+-]?(?:\d+\.?\d*|\.\d+)[eE][+-]?\d+", compact):
        try:
            value = Decimal(compact)
        except InvalidOperation:
            return compact
        if value == value.to_integral_value():
            return format(value.quantize(Decimal(1)), "f")
    return compact
def normalize_id(value):
    if value is None:
        return None
    subject_id, _ = parse_age_suffix(str(value).strip())
    if not subject_id or subject_id.lower() == "nan":
        return None
    numeric_text = normalize_numeric_id_text(subject_id)
    if not re.search(r"[A-Za-z]", numeric_text):
        digits = re.sub(r"\D", "", numeric_text)
        if not digits:
            return None
        return digits.lstrip("0") or "0"
    if re.search(r"[A-Za-z]", subject_id):
        text = re.sub(r"[^A-Za-z0-9]", "", subject_id).upper()
        return text or None
    digits = re.sub(r"\D", "", subject_id)
    if not digits:
        return None
    return digits.lstrip("0") or "0"


def normalize_status(value):
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text or text == "nan":
        return ""
    if "question" in text or "ques" in text:
        return "questionable"
    if "fail" in text:
        return "fail"
    if "pass" in text:
        return "pass"
    return text


def normalize_colname(col):
    return re.sub(r"[\s_\-]+", "", str(col).strip().lower())


def normalize_sheet_name(name):
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", str(name).strip().lower())


def read_excel_ignore_broken_styles(excel_path, **kwargs):
    import pandas as pd

    try:
        return pd.read_excel(excel_path, dtype=str, **kwargs)
    except Exception as exc:
        message = str(exc)
        if "openpyxl.styles.fills.Fill" not in message and "expected <class" not in message:
            raise
        with tempfile.TemporaryDirectory() as td:
            fixed_path = Path(td) / (Path(excel_path).stem + "_no_styles.xlsx")
            with ZipFile(excel_path, "r") as zin:
                with ZipFile(fixed_path, "w", ZIP_DEFLATED) as zout:
                    for item in zin.infolist():
                        if item.filename != "xl/styles.xml":
                            zout.writestr(item, zin.read(item.filename))
            return pd.read_excel(fixed_path, dtype=str, **kwargs)


def find_column(df, exact_aliases, contains_aliases):
    for col in df.columns:
        norm = normalize_colname(col)
        if norm in exact_aliases:
            return col
    for col in df.columns:
        norm = normalize_colname(col)
        if any(alias in norm for alias in contains_aliases):
            return col
    return None


def detect_id_t1_columns(df):
    id_col = find_column(
        df,
        {
            "subjectid", "subnum", "subject", "id", "caseid", "subid", "subname",
            "subjectname", "participant", "participantid", "participantname", "scanid",
            "studyid", "patientid", "编号", "受试者", "受试者编号", "被试", "被试编号", "病例号",
        },
        ["subjectid", "subnum", "subject", "participant", "caseid", "subid", "subname", "scanid", "studyid", "patientid", "编号", "受试者", "被试", "病例"],
    )
    t1_col = find_column(
        df,
        {"t1w", "t1", "t1qc", "t1status", "t1wstatus", "t1visualqc", "visualqc", "qcstatus", "imageqc"},
        ["t1w", "t1qc", "t1status", "t1wstatus", "t1visual", "visualqc", "qcstatus", "imageqc"],
    )
    if id_col is None or t1_col is None:
        raise ValueError(f"cannot detect ID/T1w columns from {list(df.columns)}")
    return id_col, t1_col


def classify_cbcp_site(subject_id):
    text, _ = parse_age_suffix(subject_id)
    if re.match(r"^N\d+[_\- ]?\d+", text, flags=re.IGNORECASE):
        return "xm"
    if re.search(r"[A-Za-z]", text):
        return None
    digits = re.sub(r"\D", "", text)
    if digits.startswith("04") or (len(digits) == 9 and digits.startswith("4")):
        return "cz"
    if digits.startswith("01") or (len(digits) == 9 and digits.startswith("1")):
        return "skd"
    return None


def is_cbcp_excel(excel_path):
    return "cbcp" in Path(excel_path).name.lower()


def find_cbcp_sheet(sheets, site_key):
    aliases = {
        "xm": ["xm_Allqc", "xmh_Allqc", "site2_xmh"],
        "skd": ["skd_Allqc", "stu_Allqc", "site1_stu"],
        "cz": ["cz_Allqc", "czh_Allqc", "site3_czh"],
    }[site_key]
    normalized = {normalize_sheet_name(name): name for name in sheets}
    for alias in aliases:
        hit = normalized.get(normalize_sheet_name(alias))
        if hit:
            return hit
    for name in sheets:
        norm = normalize_sheet_name(name)
        if site_key == "xm" and "xm" in norm and "allqc" in norm:
            return name
        if site_key == "skd" and ("skd" in norm or "stu" in norm) and "allqc" in norm:
            return name
        if site_key == "cz" and ("cz" in norm or "czh" in norm) and "allqc" in norm:
            return name
    return None


def add_status(mapping, key, item):
    if key and key not in mapping:
        mapping[key] = item


def load_status_from_df(df, source_sheet, site_key=None):
    id_col, t1_col = detect_id_t1_columns(df)
    mapping = {}
    invalid = []
    for idx, row in df.iterrows():
        raw_id = row.get(id_col)
        key = normalize_id(raw_id)
        if key is None:
            continue
        item = {
            "raw_id": str(raw_id).strip(),
            "t1w": str(row.get(t1_col, "")).strip(),
            "t1w_norm": normalize_status(row.get(t1_col)),
            "source_sheet": source_sheet,
        }
        add_status(mapping, key, item)
        raw = str(raw_id).strip()
        if site_key == "xm" and "_" in raw:
            add_status(mapping, normalize_id(raw.split("_", 1)[1]), item)
        if not item["t1w_norm"]:
            invalid.append(f"{source_sheet}:row {idx + 2}:{key}:empty T1w")
    return mapping, invalid


def load_status_maps(excel_path):
    sheets = read_excel_ignore_broken_styles(excel_path, sheet_name=None)
    invalid = []
    if is_cbcp_excel(excel_path):
        site_maps = {}
        for site_key in ["xm", "skd", "cz"]:
            sheet_name = find_cbcp_sheet(sheets, site_key)
            if sheet_name is None:
                site_maps[site_key] = {}
                continue
            mapping, bad = load_status_from_df(sheets[sheet_name], sheet_name, site_key=site_key)
            site_maps[site_key] = mapping
            invalid.extend(bad)
        return {"mode": "cbcp", "site_maps": site_maps}, invalid
    mapping = {}
    for sheet_name, df in sheets.items():
        try:
            sheet_map, bad = load_status_from_df(df, sheet_name)
        except ValueError:
            continue
        mapping.update(sheet_map)
        invalid.extend(bad)
    return {"mode": "generic", "mapping": mapping}, invalid


def find_default_qc_excel(batch_dir, pipeline_dir=None):
    names = ["CBCP_QC.xlsx", "ASD_QC.xlsx"]
    candidates = []
    qc_dir = os.environ.get("SMRI_QC_DIR")
    if qc_dir:
        for name in names:
            candidates.append(Path(qc_dir) / name)
    for name in names:
        candidates.append(batch_dir / "manifests" / name)
        candidates.append(batch_dir / name)
    if pipeline_dir is not None:
        for name in names:
            candidates.append(pipeline_dir / name)
            candidates.append(pipeline_dir / "manifests" / name)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def lookup_status(status_maps, subject_name):
    subject_id, _ = parse_age_suffix(subject_name)
    if status_maps["mode"] == "cbcp":
        site_key = classify_cbcp_site(subject_id)
        if site_key is None:
            return None, "cannot classify CBCP site"
        keys = [normalize_id(subject_id)]
        if site_key == "xm" and "_" in subject_id:
            keys.append(normalize_id(subject_id.split("_", 1)[1]))
        for key in keys:
            item = status_maps["site_maps"].get(site_key, {}).get(key)
            if item:
                return item, f"matched CBCP site={site_key} key={key}"
        return None, f"not found in CBCP site={site_key}"
    item = status_maps["mapping"].get(normalize_id(subject_id))
    if item:
        return item, "matched"
    return None, "not found in QC Excel"


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "branch",
        "subject_name",
        "subject_id",
        "qc_status",
        "raw_qc_id",
        "match_reason",
        "status",
        "error",
        "source_sheet",
        "source_dir",
        "raw_dir",
        "input_dir",
        "raw_shape",
        "input_shape",
        "resize_threshold",
        "bbox_start",
        "bbox_stop",
        "target_offset",
        "target_shape",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def copytree_if_needed(src, dst):
    if dst.exists():
        return "skipped_exists"
    shutil.copytree(src, dst)
    return "copied"


def shape_text(shape):
    return "x".join(str(int(x)) for x in shape)


def foreground_bbox(data, threshold):
    coords = np.argwhere(data > threshold)
    if coords.size == 0:
        raise ValueError("T1_acpc.nii.gz has no foreground voxels")
    starts = coords.min(axis=0)
    stops = coords.max(axis=0) + 1
    return starts, stops


def choose_bbox(data, target_shape):
    max_value = float(np.nanmax(data))
    if not np.isfinite(max_value) or max_value <= 0:
        raise ValueError("T1_acpc.nii.gz has no positive finite voxels")
    thresholds = [0.0, max_value * 1e-8, max_value * 1e-7, max_value * 1e-6, max_value * 1e-5, max_value * 1e-4]
    last_shape = None
    for threshold in thresholds:
        starts, stops = foreground_bbox(data, threshold)
        crop_shape = tuple(int(x) for x in (stops - starts))
        last_shape = crop_shape
        if all(crop_shape[i] <= target_shape[i] for i in range(3)):
            return starts, stops, threshold
    raise ValueError(
        f"foreground bbox {shape_text(last_shape)} exceeds moAR-Diff input shape {shape_text(target_shape)}"
    )


def crop_pad_with_metadata(data, target_shape):
    starts, stops, threshold = choose_bbox(data, target_shape)
    cropped = data[starts[0]:stops[0], starts[1]:stops[1], starts[2]:stops[2]]
    crop_shape = cropped.shape
    output = np.zeros(target_shape, dtype=np.float32)
    offsets = [(target_shape[i] - crop_shape[i]) // 2 for i in range(3)]
    output[
        offsets[0]:offsets[0] + crop_shape[0],
        offsets[1]:offsets[1] + crop_shape[1],
        offsets[2]:offsets[2] + crop_shape[2],
    ] = cropped.astype(np.float32, copy=False)
    metadata = {
        "raw_shape": [int(x) for x in data.shape[:3]],
        "target_shape": [int(x) for x in target_shape],
        "bbox_start": [int(x) for x in starts],
        "bbox_stop": [int(x) for x in stops],
        "target_offset": [int(x) for x in offsets],
        "resize_threshold": float(threshold),
    }
    return output, metadata


def crop_pad_to_shape(data, target_shape):
    output, _ = crop_pad_with_metadata(data, target_shape)
    return output


def nifti_shape(path):
    return tuple(int(x) for x in nib.load(str(path)).shape[:3])


def prepare_input(src_dir, input_dir, target_shape=MOARDIFF_INPUT_SHAPE):
    src = src_dir / "T1_acpc.nii.gz"
    result = {
        "status": "",
        "raw_shape": "",
        "input_shape": "",
        "resize_threshold": "",
        "bbox_start": "",
        "bbox_stop": "",
        "target_offset": "",
        "target_shape": shape_text(target_shape),
    }
    if not src.is_file():
        raise FileNotFoundError(f"missing T1_acpc.nii.gz: {src}")
    image = nib.load(str(src))
    raw_shape = tuple(int(x) for x in image.shape[:3])
    result["raw_shape"] = shape_text(raw_shape)
    input_dir.mkdir(parents=True, exist_ok=True)
    dst = input_dir / "T1.nii.gz"
    existed_before = dst.exists()
    if dst.is_file() and dst.stat().st_size > 0:
        existing_shape = nifti_shape(dst)
        result["input_shape"] = shape_text(existing_shape)
        if existing_shape == tuple(target_shape):
            _, metadata = crop_pad_with_metadata(image.get_fdata(dtype=np.float32), tuple(target_shape))
            (input_dir / "resize_meta.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            result["resize_threshold"] = f"{metadata['resize_threshold']:.8g}"
            result["bbox_start"] = ",".join(str(x) for x in metadata["bbox_start"])
            result["bbox_stop"] = ",".join(str(x) for x in metadata["bbox_stop"])
            result["target_offset"] = ",".join(str(x) for x in metadata["target_offset"])
            result["status"] = "skipped_exists"
            return result
    data = image.get_fdata(dtype=np.float32)
    model_input, metadata = crop_pad_with_metadata(data, tuple(target_shape))
    nib.Nifti1Image(model_input, image.affine, image.header).to_filename(str(dst))
    (input_dir / "resize_meta.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    result["input_shape"] = shape_text(model_input.shape)
    result["resize_threshold"] = f"{metadata['resize_threshold']:.8g}"
    result["bbox_start"] = ",".join(str(x) for x in metadata["bbox_start"])
    result["bbox_stop"] = ",".join(str(x) for x in metadata["bbox_stop"])
    result["target_offset"] = ",".join(str(x) for x in metadata["target_offset"])
    result["status"] = "resized_existing" if existed_before else "copied_resized"
    return result



def process_all_pass(batch_dir):
    (batch_dir / "manifests").mkdir(parents=True, exist_ok=True)
    rows = []
    for branch in ["T1T2", "justT1"]:
        root = batch_dir / "4_results" / branch
        if not root.is_dir():
            continue
        for subject_dir in sorted([p for p in root.iterdir() if p.is_dir() and p.name != "qc"], key=lambda p: p.name):
            subject_id, _ = parse_age_suffix(subject_dir.name)
            rows.append(
                {
                    "branch": branch,
                    "subject_name": subject_dir.name,
                    "subject_id": subject_id,
                    "qc_status": "pass",
                    "raw_qc_id": subject_id,
                    "match_reason": "qc-mode all-pass",
                    "status": "pass_not_selected",
                    "error": "",
                    "source_sheet": "all-pass",
                    "source_dir": str(subject_dir),
                    "raw_dir": str(batch_dir / "5_questionable" / "raw" / subject_dir.name),
                    "input_dir": str(batch_dir / "5_questionable" / "input" / subject_dir.name),
                    "raw_shape": "",
                    "input_shape": "",
                    "resize_threshold": "",
                    "bbox_start": "",
                    "bbox_stop": "",
                    "target_offset": "",
                    "target_shape": "",
                }
            )
    write_csv(batch_dir / "manifests" / SUMMARY_NAME, rows)
    (batch_dir / "manifests" / "20_questionable_qc_source.txt").write_text("all-pass\n", encoding="utf-8")
    return rows

def process(batch_dir, excel_path):
    (batch_dir / "manifests").mkdir(parents=True, exist_ok=True)
    status_maps, invalid = load_status_maps(excel_path)
    rows = []
    for branch in ["T1T2", "justT1"]:
        root = batch_dir / "4_results" / branch
        if not root.is_dir():
            continue
        for subject_dir in sorted([p for p in root.iterdir() if p.is_dir() and p.name != "qc"], key=lambda p: p.name):
            subject_id, _ = parse_age_suffix(subject_dir.name)
            item, match_reason = lookup_status(status_maps, subject_dir.name)
            row = {
                "branch": branch,
                "subject_name": subject_dir.name,
                "subject_id": subject_id,
                "qc_status": "",
                "raw_qc_id": "",
                "match_reason": match_reason,
                "status": "",
                "error": "",
                "source_sheet": "",
                "source_dir": str(subject_dir),
                "raw_dir": str(batch_dir / "5_questionable" / "raw" / subject_dir.name),
                "input_dir": str(batch_dir / "5_questionable" / "input" / subject_dir.name),
                "raw_shape": "",
                "input_shape": "",
                "resize_threshold": "",
                "bbox_start": "",
                "bbox_stop": "",
                "target_offset": "",
                "target_shape": "",
            }
            if item is None:
                row["status"] = "failed"
                row["error"] = match_reason
                rows.append(row)
                continue
            row["qc_status"] = item["t1w_norm"]
            row["raw_qc_id"] = item["raw_id"]
            row["match_reason"] = match_reason
            row["source_sheet"] = item["source_sheet"]
            if item["t1w_norm"] == "pass":
                row["status"] = "pass_not_selected"
                rows.append(row)
                continue
            if item["t1w_norm"] not in {"fail", "questionable"}:
                row["status"] = "warning"
                row["error"] = f"unknown T1w status: {item['t1w']}"
                rows.append(row)
                continue
            if not (subject_dir / "T1_acpc.nii.gz").is_file():
                row["status"] = "failed"
                row["error"] = "missing T1_acpc.nii.gz"
                rows.append(row)
                continue
            try:
                copytree_if_needed(subject_dir, Path(row["raw_dir"]))
                input_result = prepare_input(subject_dir, Path(row["input_dir"]))
                row["raw_shape"] = input_result["raw_shape"]
                row["input_shape"] = input_result["input_shape"]
                row["resize_threshold"] = input_result["resize_threshold"]
                row["bbox_start"] = input_result["bbox_start"]
                row["bbox_stop"] = input_result["bbox_stop"]
                row["target_offset"] = input_result["target_offset"]
                row["target_shape"] = input_result["target_shape"]
                row["status"] = "selected_for_denoise"
            except Exception as exc:
                row["status"] = "failed"
                row["error"] = str(exc)
            rows.append(row)
    if invalid:
        (batch_dir / "manifests" / "20_questionable_invalid_rows.txt").write_text(
            "\n".join(invalid), encoding="utf-8"
        )
    write_csv(batch_dir / "manifests" / SUMMARY_NAME, rows)
    (batch_dir / "manifests" / "20_questionable_qc_source.txt").write_text(str(excel_path) + "\n", encoding="utf-8")
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--pipeline-dir")
    parser.add_argument("--qc-excel")
    parser.add_argument(
        "--qc-mode",
        choices=["visual", "all-pass"],
        default="visual",
        help="visual reads T1 QC status from Excel; all-pass treats every ACPC subject as pass and skips denoising selection.",
    )
    args = parser.parse_args(argv)
    batch_dir = Path(args.batch_dir).resolve()
    pipeline_dir = Path(args.pipeline_dir).resolve() if args.pipeline_dir else None
    excel_path = Path(args.qc_excel).resolve() if args.qc_excel else find_default_qc_excel(batch_dir, pipeline_dir)
    if args.qc_mode == "all-pass":
        rows = process_all_pass(batch_dir)
        path = batch_dir / "manifests" / SUMMARY_NAME
        print(f"Wrote {path}")
        print("Selected for denoise: 0")
        return 0
    if excel_path is None or not excel_path.is_file():
        print("Missing QC Excel for questionable selection. Use --qc-mode all-pass for external data without visual QC.", file=sys.stderr)
        return 2
    try:
        rows = process(batch_dir, excel_path)
    except ImportError as exc:
        print("Missing pandas/openpyxl. Install the sMRI_pipeline_win environment first.", file=sys.stderr)
        raise SystemExit(2) from exc
    path = batch_dir / "manifests" / SUMMARY_NAME
    selected = sum(1 for row in rows if row["status"] == "selected_for_denoise")
    print(f"Wrote {path}")
    print(f"Selected for denoise: {selected}")
    return 1 if any(row["status"] == "failed" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())







