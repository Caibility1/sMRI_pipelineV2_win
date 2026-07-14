#!/usr/bin/env python3
"""Write a readable postprocessing report for presurf/recon."""

import argparse
import csv
from collections import Counter
from datetime import datetime
from pathlib import Path


def read_csv(path):
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def counts(rows):
    return Counter(row.get("status", "") or "blank" for row in rows)


def fmt(counter):
    if not counter:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counter.items()))


def failed_lines(rows):
    out = []
    for row in rows:
        if row.get("status") in {"failed", "warning"}:
            out.append(f"- `{row.get('subject_name', 'unknown')}`: {row.get('status')}; {row.get('error', '')}")
    return out


def add_section(lines, title, path, rows):
    lines.extend([f"## {title}", "", f"- File: `{path.name}`", f"- Rows: {len(rows)}", f"- Status counts: {fmt(counts(rows))}"])
    bad = failed_lines(rows)
    if bad:
        lines.append("- Failed/warning subjects:")
        lines.extend(bad[:80])
        if len(bad) > 80:
            lines.append(f"- ... {len(bad) - 80} more")
    lines.append("")


def build_report(batch_dir, report_path=None):
    manifest = batch_dir / "manifests"
    if report_path is None:
        logs = batch_dir / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        out = logs / "postprocessing_report.md"
    else:
        out = Path(report_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# sMRI postprocessing report: {batch_dir.name}",
        "",
        f"- Batch dir: `{batch_dir}`",
        f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
    ]
    submitted = read_csv(manifest / "submitted_post_jobs.csv") + read_csv(manifest / "submitted_questionable_post_jobs.csv")
    if submitted:
        lines.extend(["## Submitted jobs", ""])
        for row in submitted:
            lines.append("- " + ", ".join(f"{key}={value}" for key, value in row.items()))
        lines.append("")
    for title, filename in [
        ("30 presurf", "30_presurf_summary.csv"),
        ("40 recon", "40_recon_summary.csv"),
        ("30 questionable presurf", "30_questionable_presurf_summary.csv"),
        ("40 questionable recon", "40_questionable_recon_summary.csv"),
    ]:
        path = manifest / filename
        rows = read_csv(path)
        if rows or filename in {"30_presurf_summary.csv", "40_recon_summary.csv"}:
            add_section(lines, title, path, rows)
    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--report-path")
    args = parser.parse_args(argv)
    out = build_report(Path(args.batch_dir).resolve(), report_path=args.report_path)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
