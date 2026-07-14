#!/usr/bin/env python3
"""Rename subject folders by adding a trailing _<age>mo suffix from a QC Excel file."""

import argparse
import csv
from decimal import Decimal, InvalidOperation
import os
import re
import sys
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


SUMMARY_NAME = "00_age_summary.csv"
AGE_SUFFIX_RE = re.compile(r"^(?P<subject_id>.+)_(?P<age_month>\d{1,3})mo$", re.IGNORECASE)


def parse_age_suffix(name):
    match = AGE_SUFFIX_RE.match(str(name).strip())
    if not match:
        return None
    return match.group("subject_id"), match.group("age_month")


def clean_subject_name(name):
    parsed = parse_age_suffix(name)
    return parsed[0] if parsed else str(name).strip()



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
    text = clean_subject_name(str(value).strip())
    if not text or text.lower() == "nan":
        return None
    numeric_text = normalize_numeric_id_text(text)
    if not re.search(r"[A-Za-z]", numeric_text):
        digits = re.sub(r"\D", "", numeric_text)
        if not digits:
            return None
        stripped = digits.lstrip("0")
        return stripped or "0"
    if re.search(r"[A-Za-z]", text):
        normalized = re.sub(r"[^A-Za-z0-9]", "", text).upper()
        return normalized or None
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    stripped = digits.lstrip("0")
    return stripped or "0"


def normalize_age(value):
    if value is None:
        raise ValueError("empty age")
    text = str(value).strip().lower()
    if not text or text == "nan":
        raise ValueError("empty age")
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        raise ValueError(f"cannot parse age: {value}")
    number = float(match.group(0))
    if not number.is_integer():
        raise ValueError(f"age must be integer months: {value}")
    month = int(number)
    if month < 0 or month > 999:
        raise ValueError(f"age out of range: {value}")
    return str(month)


def normalize_colname(col):
    return re.sub(r"[\s_\-]+", "", str(col).strip().lower())


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


def detect_columns(df):
    id_aliases = {
        "subnum", "subjectid", "subject", "id", "caseid", "subid", "subname",
        "subjectname", "participant", "participantid", "participantname", "scanid",
        "studyid", "patientid", "编号", "受试者", "受试者编号", "被试", "被试编号", "病例号",
    }
    id_contains = ["subnum", "subject", "participant", "caseid", "subid", "subname", "scanid", "studyid", "patientid", "编号", "受试者", "被试", "病例"]
    age_aliases = {
        "month", "months", "age", "mo", "monthold", "monthsold", "agemonth",
        "agemonths", "ageinmonths", "scanage", "scanagemonth", "scanagemonths",
        "月龄", "月", "年龄月", "扫描月龄",
    }
    age_contains = ["month", "agemonth", "ageinmonth", "scanage", "月龄", "年龄", "月"]
    id_col = None
    age_col = None
    for col in df.columns:
        norm = normalize_colname(col)
        if id_col is None and (norm in id_aliases or any(alias in norm for alias in id_contains) or norm == "id"):
            id_col = col
        if age_col is None and (norm in age_aliases or any(alias in norm for alias in age_contains) or norm == "age"):
            age_col = col
    if id_col is None or age_col is None:
        raise ValueError(f"cannot detect ID/age columns from {list(df.columns)}")
    return id_col, age_col


def normalize_sheet_name(name):
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", str(name).strip().lower())


def is_cbcp_excel(excel_path):
    return "cbcp" in Path(excel_path).name.lower()


def classify_cbcp_site(subject_id):
    text = clean_subject_name(subject_id)
    if re.match(r"^N\d+[_\- ]?\d+", text, flags=re.IGNORECASE):
        return "xm"
    if re.search(r"[A-Za-z]", text):
        return None
    digits = re.sub(r"\D", "", text)
    if digits.startswith("04"):
        return "cz"
    if digits.startswith("01"):
        return "skd"
    return None


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


def add_mapping(mapping, norm_id, age, duplicates):
    previous = mapping.get(norm_id)
    if previous is not None:
        duplicates.append(f"{norm_id}:{previous}!={age}")
        return
    mapping[norm_id] = age


def load_map_from_dataframe(df, site_key=None):
    id_col, age_col = detect_columns(df)
    mapping = {}
    duplicates = []
    invalid_rows = []
    for idx, row in df.iterrows():
        raw_id = row.get(id_col)
        norm_id = normalize_id(raw_id)
        if norm_id is None:
            continue
        try:
            age = normalize_age(row.get(age_col))
        except Exception as exc:
            invalid_rows.append(f"row {idx + 2}:{norm_id}:{exc}")
            continue
        add_mapping(mapping, norm_id, age, duplicates)
        raw = str(raw_id).strip()
        if site_key == "xm" and "_" in raw:
            suffix = normalize_id(raw.split("_", 1)[1])
            if suffix:
                add_mapping(mapping, suffix, age, duplicates)
    return mapping, duplicates, invalid_rows


def load_age_maps(excel_path):
    try:
        sheets = read_excel_ignore_broken_styles(excel_path, sheet_name=None)
    except ImportError as exc:
        raise SystemExit("Missing pandas/openpyxl. Install the sMRI_pipeline_win environment first.") from exc

    if is_cbcp_excel(excel_path):
        site_maps = {}
        invalid_rows = []
        for site_key in ["xm", "skd", "cz"]:
            sheet_name = find_cbcp_sheet(sheets, site_key)
            if sheet_name is None:
                site_maps[site_key] = {}
                continue
            mapping, duplicates, invalid = load_map_from_dataframe(sheets[sheet_name], site_key=site_key)
            site_maps[site_key] = mapping
            invalid_rows.extend([f"{sheet_name}:{item}" for item in invalid])
            invalid_rows.extend([f"{sheet_name}:duplicate kept first:{item}" for item in duplicates[:200]])
        return {"mode": "cbcp", "site_maps": site_maps}, invalid_rows

    mapping = {}
    invalid_rows = []
    for sheet_name, df in sheets.items():
        try:
            sheet_map, duplicates, invalid = load_map_from_dataframe(df)
        except ValueError:
            continue
        mapping.update(sheet_map)
        invalid_rows.extend([f"{sheet_name}:{item}" for item in invalid])
        invalid_rows.extend([f"{sheet_name}:duplicate kept first:{item}" for item in duplicates[:200]])
    return {"mode": "generic", "mapping": mapping}, invalid_rows


def find_age(age_maps, subject_id):
    if age_maps["mode"] == "cbcp":
        site_key = classify_cbcp_site(subject_id)
        if site_key is None:
            return None, "cannot classify CBCP site from subject id"
        mapping = age_maps["site_maps"].get(site_key, {})
        keys = [normalize_id(subject_id)]
        if site_key == "xm" and "_" in subject_id:
            keys.append(normalize_id(subject_id.split("_", 1)[1]))
        for key in keys:
            if key in mapping:
                return mapping[key], f"matched CBCP site={site_key} key={key}"
        return None, f"not found in CBCP site={site_key} Allqc sheet"
    age = age_maps["mapping"].get(normalize_id(subject_id))
    if age is None:
        return None, "not found in QC Excel"
    return age, "matched"


def default_qc_candidates(batch_dir, pipeline_dir=None):
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
    return candidates


def find_default_qc_excel(batch_dir, pipeline_dir=None):
    for candidate in default_qc_candidates(batch_dir, pipeline_dir=pipeline_dir):
        if candidate.is_file():
            return candidate
    return None


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["old_name", "new_name", "subject_id", "age_month", "status", "error"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)



def process_existing_age(data_dir, summary_path):
    rows = []
    failures = 0
    for folder in sorted([p for p in data_dir.iterdir() if p.is_dir()], key=lambda p: p.name):
        parsed = parse_age_suffix(folder.name)
        if parsed is None:
            rows.append(
                {
                    "old_name": folder.name,
                    "new_name": "",
                    "subject_id": folder.name,
                    "age_month": "",
                    "status": "failed",
                    "error": "missing _<age>mo suffix and no age Excel was supplied",
                }
            )
            failures += 1
            continue
        subject_id, age = parsed
        rows.append(
            {
                "old_name": folder.name,
                "new_name": folder.name,
                "subject_id": subject_id,
                "age_month": age,
                "status": "skipped",
                "error": "",
            }
        )
    write_csv(summary_path, rows)
    return failures

def process(data_dir, excel_path, summary_path, dry_run=False):
    age_maps, invalid_rows = load_age_maps(excel_path)
    rows = []
    failures = 0
    for folder in sorted([p for p in data_dir.iterdir() if p.is_dir()], key=lambda p: p.name):
        parsed = parse_age_suffix(folder.name)
        subject_id = parsed[0] if parsed else folder.name
        existing_age = parsed[1] if parsed else None
        norm_id = normalize_id(subject_id)
        age, match_reason = find_age(age_maps, subject_id)
        row = {
            "old_name": folder.name,
            "new_name": "",
            "subject_id": subject_id,
            "age_month": age or "",
            "status": "",
            "error": "",
        }
        if age is None:
            row["status"] = "failed"
            row["error"] = f"{match_reason}: {subject_id}"
            failures += 1
            rows.append(row)
            continue
        if existing_age is not None and existing_age != age:
            row["status"] = "failed"
            row["error"] = f"age conflict folder={existing_age}mo excel={age}mo"
            failures += 1
            rows.append(row)
            continue
        new_name = f"{subject_id}_{age}mo"
        new_path = folder.parent / new_name
        row["new_name"] = new_name
        if folder.name == new_name:
            row["status"] = "skipped"
            rows.append(row)
            continue
        if new_path.exists():
            row["status"] = "failed"
            row["error"] = f"target folder exists: {new_path}"
            failures += 1
            rows.append(row)
            continue
        if not dry_run:
            folder.rename(new_path)
        row["status"] = "renamed"
        rows.append(row)
    if invalid_rows:
        (summary_path.parent / "00_age_invalid_rows.txt").write_text("\n".join(invalid_rows), encoding="utf-8")
    write_csv(summary_path, rows)
    return failures


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--qc-excel")
    parser.add_argument("--pipeline-dir")
    parser.add_argument(
        "--age-source",
        choices=["auto", "excel", "folder"],
        default="auto",
        help="Where to get subject age months. auto uses Excel when available, otherwise existing _<age>mo folder suffixes.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    batch_dir = Path(args.batch_dir).resolve()
    data_dir = batch_dir / "1_T2toT1" / "data"
    pipeline_dir = Path(args.pipeline_dir).resolve() if args.pipeline_dir else None
    excel_path = Path(args.qc_excel).resolve() if args.qc_excel else find_default_qc_excel(batch_dir, pipeline_dir)
    if not data_dir.is_dir():
        print(f"Missing data directory: {data_dir}", file=sys.stderr)
        return 2
    if args.age_source == "folder" or (args.age_source == "auto" and (excel_path is None or not excel_path.is_file())):
        failures = process_existing_age(data_dir, batch_dir / "manifests" / SUMMARY_NAME)
        (batch_dir / "manifests" / "00_age_qc_source.txt").write_text("folder_suffix\n", encoding="utf-8")
        print(f"Wrote {batch_dir / 'manifests' / SUMMARY_NAME}")
        if failures:
            print(f"Age suffix failures: {failures}", file=sys.stderr)
            return 1
        return 0
    if excel_path is None or not excel_path.is_file():
        print("Missing age/QC Excel. Use --age-source folder if folders already end with _<age>mo.", file=sys.stderr)
        return 2
    failures = process(data_dir, excel_path, batch_dir / "manifests" / SUMMARY_NAME, dry_run=args.dry_run)
    (batch_dir / "manifests" / "00_age_qc_source.txt").write_text(str(excel_path) + "\n", encoding="utf-8")
    print(f"Wrote {batch_dir / 'manifests' / SUMMARY_NAME}")
    if failures:
        print(f"Age suffix failures: {failures}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())







