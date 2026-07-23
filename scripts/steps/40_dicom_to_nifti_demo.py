#!/usr/bin/env python3
"""Convert teaching DICOM folders and conservatively select structural MRI series."""


import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path


EXCLUDED_TERMS = (
    "scout",
    "localizer",
    "survey",
    "locator",
    "motion curve",
    "motioncurve",
    "moco",
    "field map",
    "fieldmap",
    "phase",
    "screen save",
    "screensave",
)
T1_TERMS = ("t1", "mprage", "mp-rage", "bravo", "spgr", "tfl3d")
T2_TERMS = ("t2", "tse", "turbo spin echo")


class AmbiguousSeriesError(RuntimeError):
    pass


class SeriesCandidate:
    __slots__ = ("series_number", "nifti_path", "json_path", "classification", "score")

    def __init__(self, series_number, nifti_path, json_path, classification, score):
        self.series_number = str(series_number)
        self.nifti_path = nifti_path
        self.json_path = json_path
        self.classification = classification
        self.score = int(score)


def _text(metadata):
    fields = ("SeriesDescription", "ProtocolName", "SequenceName", "ScanningSequence")
    return " ".join(str(metadata.get(field, "")) for field in fields).lower()


def _image_types(metadata):
    value = metadata.get("ImageType", [])
    if isinstance(value, str):
        value = value.replace("\\", " ").split()
    return {str(item).strip().lower() for item in value}


def classify_series(metadata):
    """Classify one dcm2niix JSON sidecar without guessing ambiguous anatomy."""
    text = _text(metadata)
    text_tokens = text.replace("_", " ").replace("-", " ").split()
    if "ndc" in text_tokens:
        return "excluded"
    image_types = _image_types(metadata)
    if any(term in text for term in EXCLUDED_TERMS):
        return "excluded"
    if {"derived", "secondary"} & image_types:
        return "excluded"

    has_t1 = any(term in text for term in T1_TERMS)
    has_t2 = any(term in text for term in T2_TERMS)
    if has_t1 and not has_t2:
        return "t1"
    if has_t2 and not has_t1:
        return "t2"
    return "other"


def score_series(metadata, classification):
    if classification not in {"t1", "t2"}:
        return 0
    text = _text(metadata)
    image_types = _image_types(metadata)
    score = 40
    if str(metadata.get("MRAcquisitionType", "")).upper() == "3D":
        score += 20
    if any(term in text for term in ("iso", "isotropic", "mprage", "space", "bravo", "cube")):
        score += 10
    if "dc3d" in image_types:
        score += 20
    if "ndc" in text:
        score -= 20
    return score


def choose_series(candidates, modality, requested_series=None):
    matches = [candidate for candidate in candidates if candidate.classification == modality]
    if requested_series is not None:
        requested = str(requested_series).lstrip("0") or "0"
        selected = [
            candidate
            for candidate in matches
            if (candidate.series_number.lstrip("0") or "0") == requested
        ]
        if len(selected) != 1:
            raise ValueError(
                f"Requested {modality.upper()} series {requested_series!r} matched "
                f"{len(selected)} candidates"
            )
        return selected[0]
    if not matches:
        return None
    highest = max(candidate.score for candidate in matches)
    best = [candidate for candidate in matches if candidate.score == highest]
    if len(best) != 1:
        numbers = ", ".join(candidate.series_number for candidate in best)
        raise AmbiguousSeriesError(
            f"Multiple equally ranked {modality.upper()} series ({numbers}); "
            f"rerun with --{modality}-series SERIES_NUMBER"
        )
    return best[0]


def sidecar_nifti(json_path):
    base = json_path.with_suffix("")
    nii_gz = Path(str(base) + ".nii.gz")
    if nii_gz.is_file():
        return nii_gz
    nii = Path(str(base) + ".nii")
    return nii if nii.is_file() else None


def load_candidates(candidate_dir):
    candidates = []
    details = {}
    for json_path in sorted(candidate_dir.glob("*.json")):
        nifti_path = sidecar_nifti(json_path)
        if nifti_path is None:
            continue
        try:
            metadata = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARNING: cannot read {json_path}: {exc}", file=sys.stderr)
            continue
        classification = classify_series(metadata)
        series_number = str(metadata.get("SeriesNumber", json_path.stem.split("_")[0]))
        candidate = SeriesCandidate(
            series_number,
            str(nifti_path),
            str(json_path),
            classification,
            score_series(metadata, classification),
        )
        candidates.append(candidate)
        details[str(json_path)] = metadata
    return candidates, details


def run_dcm2niix(source_dir, candidate_dir, executable="dcm2niix"):
    candidate_dir.mkdir(parents=True, exist_ok=True)
    command = [
        executable,
        "-z",
        "y",
        "-b",
        "y",
        "-ba",
        "y",
        "-f",
        "%3s_%p",
        "-o",
        str(candidate_dir),
        str(source_dir),
    ]
    print("RUN:", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def _copy_selected(candidate, target_dir, modality, force=False):
    if candidate is None:
        return "not_available"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_nii = target_dir / f"{modality.upper()}.nii.gz"
    target_json = target_dir / f"{modality.upper()}.json"
    if target_nii.exists() and not force:
        return "checkpoint_exists"
    shutil.copy2(candidate.nifti_path, target_nii)
    shutil.copy2(candidate.json_path, target_json)
    return "copied"


def _write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def discover_subjects(raw_dir, requested_subjects):
    if requested_subjects:
        subjects = [raw_dir / subject for subject in requested_subjects]
    else:
        subjects = sorted((path for path in raw_dir.iterdir() if path.is_dir()), key=lambda p: p.name)
    missing = [path for path in subjects if not path.is_dir()]
    if missing:
        raise FileNotFoundError("Missing DICOM subject folders: " + ", ".join(str(path) for path in missing))
    return subjects


def resolve_raw_dir(batch_dir, raw_dir=None):
    if not raw_dir:
        return batch_dir / "0_rawdata"
    path = Path(raw_dir).expanduser()
    return path.resolve() if path.is_absolute() else batch_dir / path


def build_unselected_inventory(subject, candidates, details):
    inventory = []
    for candidate in candidates:
        metadata = details.get(str(candidate.json_path), {})
        inventory.append(
            {
                "subject": subject,
                "series_number": candidate.series_number,
                "series_description": metadata.get("SeriesDescription", ""),
                "protocol_name": metadata.get("ProtocolName", ""),
                "classification": candidate.classification,
                "score": candidate.score,
                "selected": "",
                "nifti_path": candidate.nifti_path,
                "json_path": candidate.json_path,
            }
        )
    return inventory


def process_subject(subject_dir, batch_dir, args):
    subject = subject_dir.name
    candidate_dir = batch_dir / "1_T2toT1" / "dicom_candidates" / subject
    existing_sidecars = list(candidate_dir.glob("*.json")) if candidate_dir.is_dir() else []
    if not existing_sidecars:
        run_dcm2niix(subject_dir, candidate_dir, args.dcm2niix)
    else:
        print(f"[{subject}] dcm2niix checkpoint: using {len(existing_sidecars)} existing sidecars")

    candidates, details = load_candidates(candidate_dir)
    if getattr(args, "inventory_only", False):
        inventory = build_unselected_inventory(subject, candidates, details)
        summary = {
            "subject": subject,
            "status": "inventory_complete",
            "t1_series": "",
            "t1_action": "not_selected",
            "t2_series": "",
            "t2_action": "not_selected",
            "error": "",
        }
        print(
            f"[{subject}] DICOM inventory complete: {len(candidates)} converted candidates",
            flush=True,
        )
        return inventory, summary
    t1 = choose_series(candidates, "t1", args.t1_series)
    if t1 is None:
        raise RuntimeError("No unambiguous T1-weighted series was found")
    t2 = choose_series(candidates, "t2", args.t2_series)
    target_dir = batch_dir / "1_T2toT1" / "data" / subject
    t1_action = _copy_selected(t1, target_dir, "t1", args.force)
    t2_action = _copy_selected(t2, target_dir, "t2", args.force)

    inventory = []
    for candidate in candidates:
        metadata = details.get(str(candidate.json_path), {})
        inventory.append(
            {
                "subject": subject,
                "series_number": candidate.series_number,
                "series_description": metadata.get("SeriesDescription", ""),
                "protocol_name": metadata.get("ProtocolName", ""),
                "classification": candidate.classification,
                "score": candidate.score,
                "selected": (
                    "T1" if candidate is t1 else "T2" if candidate is t2 else ""
                ),
                "nifti_path": candidate.nifti_path,
                "json_path": candidate.json_path,
            }
        )
    summary = {
        "subject": subject,
        "status": "complete",
        "t1_series": t1.series_number,
        "t1_action": t1_action,
        "t2_series": t2.series_number if t2 else "",
        "t2_action": t2_action,
        "error": "",
    }
    print(
        f"[{subject}] DICOM conversion complete: T1={t1.series_number}, "
        f"T2={t2.series_number if t2 else 'not available'}",
        flush=True,
    )
    return inventory, summary


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Convert raw DICOM folders and select T1/T2 series conservatively."
    )
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--raw-dir", help="Absolute path or path relative to BATCH_DIR (default: 0_rawdata)")
    parser.add_argument("--subject", action="append", default=[])
    parser.add_argument("--dcm2niix", default="dcm2niix")
    parser.add_argument("--t1-series")
    parser.add_argument("--t2-series")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--inventory-only", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    batch_dir = Path(args.batch_dir).expanduser().resolve()
    raw_dir = resolve_raw_dir(batch_dir, args.raw_dir)
    if not raw_dir.is_dir():
        print(f"Missing raw DICOM directory: {raw_dir}", file=sys.stderr)
        return 2

    inventory_rows = []
    summary_rows = []
    failures = 0
    try:
        subjects = discover_subjects(raw_dir, args.subject)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not subjects:
        print(f"No subject folders found under {raw_dir}", file=sys.stderr)
        return 2

    for subject_dir in subjects:
        try:
            inventory, summary = process_subject(subject_dir, batch_dir, args)
            inventory_rows.extend(inventory)
            summary_rows.append(summary)
        except Exception as exc:
            failures += 1
            summary_rows.append(
                {
                    "subject": subject_dir.name,
                    "status": "failed",
                    "t1_series": "",
                    "t1_action": "",
                    "t2_series": "",
                    "t2_action": "",
                    "error": str(exc),
                }
            )
            print(f"[{subject_dir.name}] FAILED: {exc}", file=sys.stderr, flush=True)

    manifests = batch_dir / "manifests"
    _write_csv(
        manifests / "00_dicom_series_inventory.csv",
        [
            "subject",
            "series_number",
            "series_description",
            "protocol_name",
            "classification",
            "score",
            "selected",
            "nifti_path",
            "json_path",
        ],
        inventory_rows,
    )
    _write_csv(
        manifests / "00_dicom_conversion_summary.csv",
        ["subject", "status", "t1_series", "t1_action", "t2_series", "t2_action", "error"],
        summary_rows,
    )
    print(f"DICOM stage complete: {len(subjects) - failures} succeeded, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
