#!/usr/bin/env python3
"""Windows/WSL2 one-stop presurf/recon entrypoint for sMRI Pipeline V2."""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "steps"))

from smri_windows_utils import (
    PipelineContext,
    add_common_args,
    build_docker_bash_command,
    build_wsl_bash_command,
    check_docker_available,
    check_wsl_available,
    normalize_external_path,
    parse_backend,
    record_status,
    run_python_step,
    run_step,
)

POST_FIELDS = ["mode", "source_dir", "target_root", "presurf_job_id", "recon_job_id"]


def write_submitted_post_jobs(path: Path, row: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=POST_FIELDS)
        writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in POST_FIELDS})


def require_wsl(ctx: PipelineContext, backend: str) -> None:
    if backend == "wsl" and not check_wsl_available(ctx):
        raise SystemExit("WSL backend requested, but wsl.exe + bash are not available.")
    if backend == "docker" and not check_docker_available():
        raise SystemExit("Docker backend requested, but Docker Desktop/Engine is not available.")


def run_wsl_job(
    ctx: PipelineContext,
    name: str,
    body: str,
    *,
    extra_env: dict[str, str | Path] | None = None,
    log_dir: Path | None = None,
) -> int:
    command = build_wsl_bash_command(ctx, body, extra_env=extra_env)
    return run_step(ctx, name, "wsl2-bash", command, log_dir=log_dir)


def run_docker_job(
    ctx: PipelineContext,
    name: str,
    image: str,
    body: str,
    *,
    extra_env: dict[str, str | Path] | None = None,
    gpus: str = "",
    log_dir: Path | None = None,
) -> int:
    command = build_docker_bash_command(ctx, image, body, extra_env=extra_env, gpus=gpus)
    return run_step(ctx, name, "docker-bash", command, log_dir=log_dir)


def build_mode(args: argparse.Namespace, batch_dir: Path) -> dict[str, object]:
    return {
        "mode": "standard",
        "source_dir": batch_dir / "6_seg",
        "target_root": batch_dir / "7_presurf",
        "report_path": batch_dir / "logs" / "postprocessing_report.md",
        "submitted_jobs": batch_dir / "manifests" / "submitted_post_jobs.csv",
        "presurf_summary": "30_presurf_summary.csv",
        "recon_summary": "40_recon_summary.csv",
    }

def write_report(ctx: PipelineContext, report_path: Path) -> None:
    run_python_step(
        ctx,
        "99_write_postprocessing_report",
        "scripts/steps/32_write_postprocessing_report_v2.py",
        "--batch-dir",
        ctx.batch_dir,
        "--report-path",
        report_path,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--Qsubmit", dest="qsubmit", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--presurf-only", action="store_true")
    parser.add_argument("--presurf-backend", type=parse_backend, default=os.environ.get("SMRI_PRESURF_BACKEND", "windows"))
    parser.add_argument("--recon-backend", type=parse_backend, default=os.environ.get("SMRI_RECON_BACKEND", "wsl"))
    parser.add_argument("--freesurfer-home", default=os.environ.get("FREESURFER_HOME", ""))
    parser.add_argument("--fs-license", default=os.environ.get("FS_LICENSE", ""))
    parser.add_argument("--recon-jobs", default=os.environ.get("SMRI_RECON_JOBS", "4"))
    parser.add_argument("--docker-tools-image", default=os.environ.get("SMRI_DOCKER_TOOLS_IMAGE", "smri_pipeline_win:tools"))
    parser.add_argument("--docker-gpus", default=os.environ.get("SMRI_DOCKER_GPUS", "none"))
    args = parser.parse_args(argv)
    if args.qsubmit:
        parser.error("--Qsubmit has been disabled. Denoised/questionable outputs must be segmented first; run standard --submit after valid 6_seg exists.")
    return args

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pipeline_dir = Path(__file__).resolve().parents[2]
    batch_dir = Path(args.batch_dir).expanduser().resolve()
    ctx = PipelineContext(
        pipeline_dir=pipeline_dir,
        batch_dir=batch_dir,
        python_bin=args.python_bin,
        wsl_distro=args.wsl_distro,
        dry_run=False,
    )
    if not batch_dir.is_dir():
        raise SystemExit(f"Batch directory does not exist: {batch_dir}")
    ctx.manifest_dir.mkdir(parents=True, exist_ok=True)

    mode = build_mode(args, batch_dir)
    source_dir = Path(mode["source_dir"])
    target_root = Path(mode["target_root"])
    report_path = Path(mode["report_path"])
    submitted_jobs = Path(mode["submitted_jobs"])
    target_root.mkdir(parents=True, exist_ok=True)
    (target_root / "logs").mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    if not source_dir.is_dir():
        write_report(ctx, report_path)
        raise SystemExit(f"Missing postprocessing input directory: {source_dir}")

    if not args.submit:
        write_report(ctx, report_path)
        print("Validation complete. Use --submit to run presurf/recon.")
        return 0

    require_wsl(ctx, args.presurf_backend)
    if not args.presurf_only:
        require_wsl(ctx, args.recon_backend)

    row = {
        "mode": str(mode["mode"]),
        "source_dir": str(source_dir),
        "target_root": str(target_root),
        "presurf_job_id": "",
        "recon_job_id": "",
    }
    exit_code = 0

    if args.presurf_backend == "windows":
        code = run_step(
            ctx,
            f"30_presurf_{mode['mode']}",
            "windows-python",
            ctx.python_step(
                "scripts/steps/30_presurf_v2.py",
                "--batch-dir",
                batch_dir,
                "--source-dir",
                source_dir,
                "--target-root",
                target_root,
                "--summary-name",
                mode["presurf_summary"],
            ),
            log_dir=target_root / "logs",
        )
        row["presurf_job_id"] = f"windows:presurf:rc{code}"
        if code != 0:
            write_submitted_post_jobs(submitted_jobs, row)
            write_report(ctx, report_path)
            return code
    elif args.presurf_backend == "wsl":
        code = run_wsl_job(
            ctx,
            f"30_presurf_{mode['mode']}",
            (
                'bash "$PIPELINE_DIR/scripts/jobs/presurf.sh" '
                f'"$BATCH_DIR" "$PIPELINE_DIR" "$SOURCE_DIR" "$TARGET_ROOT" "{mode["presurf_summary"]}"'
            ),
            extra_env={"SOURCE_DIR": source_dir, "TARGET_ROOT": target_root},
            log_dir=target_root / "logs",
        )
        row["presurf_job_id"] = f"wsl:presurf:rc{code}"
        if code != 0:
            write_submitted_post_jobs(submitted_jobs, row)
            write_report(ctx, report_path)
            return code
    elif args.presurf_backend == "docker":
        code = run_docker_job(
            ctx,
            f"30_presurf_{mode['mode']}",
            args.docker_tools_image,
            (
                'bash "$PIPELINE_DIR/scripts/jobs/presurf.sh" '
                f'"$BATCH_DIR" "$PIPELINE_DIR" "$SOURCE_DIR" "$TARGET_ROOT" "{mode["presurf_summary"]}"'
            ),
            extra_env={"SOURCE_DIR": source_dir, "TARGET_ROOT": target_root},
            log_dir=target_root / "logs",
        )
        row["presurf_job_id"] = f"docker:presurf:rc{code}"
        if code != 0:
            write_submitted_post_jobs(submitted_jobs, row)
            write_report(ctx, report_path)
            return code
    else:
        record_status(ctx, {"step": f"30_presurf_{mode['mode']}", "backend": "skip", "status": "skipped"})
        row["presurf_job_id"] = "skipped"

    if not args.presurf_only:
        if args.recon_backend == "skip":
            row["recon_job_id"] = "skipped"
            write_submitted_post_jobs(submitted_jobs, row)
            write_report(ctx, report_path)
            print(f"Postprocessing report: {report_path}")
            print(f"Submitted jobs manifest: {submitted_jobs}")
            return 0
        if args.recon_backend not in {"wsl", "docker"}:
            raise SystemExit("Recon uses FreeSurfer infant_recon_all and currently supports --recon-backend wsl, docker, or skip.")
        extra_env: dict[str, str | Path] = {"SMRI_RECON_JOBS": args.recon_jobs, "TARGET_ROOT": target_root, "REPORT_PATH": report_path}
        if args.freesurfer_home:
            extra_env["FREESURFER_HOME"] = normalize_external_path(args.freesurfer_home)
        if args.fs_license:
            extra_env["FS_LICENSE"] = normalize_external_path(args.fs_license)
        if args.recon_backend == "wsl":
            code = run_wsl_job(
                ctx,
                f"40_recon_{mode['mode']}",
                (
                    'bash "$PIPELINE_DIR/scripts/jobs/recon_all.sh" '
                    f'"$BATCH_DIR" "$PIPELINE_DIR" "$TARGET_ROOT" "{mode["recon_summary"]}" "$REPORT_PATH"'
                ),
                extra_env=extra_env,
                log_dir=target_root / "logs",
            )
            recon_code = code
            exit_code = recon_code
            row["recon_job_id"] = f"wsl:recon:rc{recon_code}"
        else:
            code = run_docker_job(
                ctx,
                f"40_recon_{mode['mode']}",
                args.docker_tools_image,
                (
                    'bash "$PIPELINE_DIR/scripts/jobs/recon_all.sh" '
                    f'"$BATCH_DIR" "$PIPELINE_DIR" "$TARGET_ROOT" "{mode["recon_summary"]}" "$REPORT_PATH"'
                ),
                extra_env=extra_env,
                gpus=args.docker_gpus,
                log_dir=target_root / "logs",
            )
            recon_code = code
            exit_code = recon_code
            row["recon_job_id"] = f"docker:recon:rc{recon_code}"
    else:
        row["recon_job_id"] = "skipped_presurf_only"

    write_submitted_post_jobs(submitted_jobs, row)
    write_report(ctx, report_path)
    print(f"Postprocessing report: {report_path}")
    print(f"Submitted jobs manifest: {submitted_jobs}")
    print(f"Presurf log: {target_root / 'logs' / ('30_presurf_' + str(mode['mode']) + '.log')}")
    if not args.presurf_only:
        print(f"Recon log: {target_root / 'logs' / ('40_recon_' + str(mode['mode']) + '.log')}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())



