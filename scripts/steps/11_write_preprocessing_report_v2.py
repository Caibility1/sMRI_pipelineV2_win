#!/usr/bin/env python3
"""Write a human-readable preprocessing report for one batch."""

import argparse
import csv
from collections import Counter
from datetime import datetime
from pathlib import Path


REPORT_NAME = "preprocessing_report.md"


def read_csv(path):
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def count_by(rows, field):
    return Counter(row.get(field, "") or "blank" for row in rows)


def fmt_counts(counter):
    if not counter:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counter.items()))


def failed_lines(rows, id_field="subject_name", status_field="status"):
    out = []
    for row in rows:
        status = row.get(status_field, "")
        if status in {"failed", "warning"}:
            sid = row.get(id_field) or row.get("subject") or row.get("old_name") or "unknown"
            err = row.get("error", "")
            out.append(f"- `{sid}`: {status}; {err}")
    return out


def section(title, body):
    return [f"## {title}", "", *body, ""]


def table_summary(name, path, rows):
    body = [f"- File: `{path.name}`"]
    if not rows:
        body.append("- Status: missing or empty")
        return section(name, body)
    body.append(f"- Rows: {len(rows)}")
    if "status" in rows[0]:
        body.append(f"- Status counts: {fmt_counts(count_by(rows, 'status'))}")
    if "branch" in rows[0]:
        body.append(f"- Branch counts: {fmt_counts(count_by(rows, 'branch'))}")
    failures = failed_lines(rows)
    if failures:
        body.append("- Failed/warning subjects:")
        body.extend(failures[:80])
        if len(failures) > 80:
            body.append(f"- ... {len(failures) - 80} more")
    return section(name, body)


def build_report(batch_dir):
    manifest = batch_dir / "manifests"
    logs = batch_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    items = [
        ("00 Age suffix", manifest / "00_age_summary.csv"),
        ("01 T1/T2 standardization", manifest / "01_copy_rename_summary.csv"),
        ("02 T2-to-T1 input", manifest / "02_t2tot1_input_summary.csv"),
        ("03 T2-to-T1 output", manifest / "03_t2tot1_output_summary.csv"),
        ("04 nnU-Net input", manifest / "04_nnunet_input_summary.csv"),
        ("05 nnU-Net output", manifest / "05_nnunet_output_summary.csv"),
        ("06 mask_all", manifest / "06_mask_all_summary.csv"),
        ("10 Split for ACPC", manifest / "10_split_for_acpc_summary.csv"),
        ("11 ACPC", manifest / "11_acpc_summary.csv"),
        ("12 ACPC QC", manifest / "12_acpc_qc_summary.csv"),
        ("20 Questionable/Fail denoise selection", manifest / "20_questionable_summary.csv"),
        ("21 Denoise submission", manifest / "21_denoise_summary.csv"),
    ]
    lines = [
        f"# sMRI preprocessing report: {batch_dir.name}",
        "",
        f"- Batch dir: `{batch_dir}`",
        f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
    ]
    submitted = read_csv(manifest / "submitted_jobs.csv")
    if submitted:
        lines.extend(section("Submitted jobs", [
            f"- File: `{(manifest / 'submitted_jobs.csv').name}`",
            *[f"- {', '.join(f'{k}={v}' for k, v in row.items())}" for row in submitted],
        ]))
    for title, path in items:
        lines.extend(table_summary(title, path, read_csv(path)))
    denoise_job = manifest / "denoise_job_id.txt"
    if denoise_job.is_file():
        lines.extend(section("Denoise job tracking", [f"- Job id: `{denoise_job.read_text(encoding='utf-8').strip()}`"]))
    out = logs / REPORT_NAME
    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", required=True)
    args = parser.parse_args(argv)
    out = build_report(Path(args.batch_dir).resolve())
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
