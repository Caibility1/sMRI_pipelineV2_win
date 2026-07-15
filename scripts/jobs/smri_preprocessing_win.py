#!/usr/bin/env python3
"""Windows/WSL2 one-stop preprocessing entrypoint for sMRI Pipeline V2."""

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
    default_moardiff_dir,
    default_nnunet_resource,
    default_template_dir,
    ensure_batch_layout,
    normalize_external_path,
    parse_backend,
    record_status,
    run_python_step,
    run_step,
)


JOB_FIELDS = [
    "reg_job_id",
    "nnunet_job_id",
    "mask_all_job_id",
    "t1t2_acpc_job_id",
    "justt1_acpc_job_id",
    "t1t2_qc_job_id",
    "justt1_qc_job_id",
    "denoise_job_id",
]


def count_csv_status(path: Path, status_value: str) -> int:
    if not path.is_file():
        return 0
    with path.open(newline="", encoding="utf-8") as f:
        return sum(1 for row in csv.DictReader(f) if row.get("status") == status_value)


def count_existing_denoise_inputs(batch_dir: Path) -> int:
    count = 0
    for root, pattern in [
        (batch_dir / "5_questionable" / "input", "*/T1.nii.gz"),
        (batch_dir / "5_questionable" / "output", "*/T1_age.nii.gz"),
    ]:
        if root.is_dir():
            count += sum(1 for _ in root.glob(pattern))
    return count


def branch_subject_count(batch_dir: Path, branch: str) -> int:
    root = batch_dir / "4_results" / branch
    if not root.is_dir():
        return 0
    return sum(1 for path in root.iterdir() if path.is_dir() and path.name != "qc")


def write_submitted_jobs(ctx: PipelineContext, jobs: dict[str, str]) -> None:
    path = ctx.manifest_dir / "submitted_jobs.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=JOB_FIELDS)
        writer.writeheader()
        writer.writerow({field: jobs.get(field, "") for field in JOB_FIELDS})


def require_wsl_if_needed(ctx: PipelineContext, *backends: str) -> None:
    if "wsl" in backends and not check_wsl_available(ctx):
        raise SystemExit(
            "WSL backend requested, but wsl.exe + bash are not available. "
            "Install WSL2 Ubuntu or change the relevant --*-backend option to skip/windows/docker."
        )
    if "docker" in backends and not check_docker_available():
        raise SystemExit(
            "Docker backend requested, but Docker Desktop/Engine is not available. "
            "Install Docker Desktop with WSL2 backend or use --*-backend wsl/windows."
        )


def run_wsl_job(
    ctx: PipelineContext,
    name: str,
    body: str,
    *,
    nnunet_resource_dir: Path | None = None,
    extra_env: dict[str, str | Path] | None = None,
    log_dir: Path | None = None,
) -> int:
    command = build_wsl_bash_command(
        ctx,
        body,
        nnunet_resource_dir=nnunet_resource_dir,
        extra_env=extra_env,
    )
    return run_step(ctx, name, "wsl2-bash", command, log_dir=log_dir)


def run_docker_job(
    ctx: PipelineContext,
    name: str,
    image: str,
    body: str,
    *,
    nnunet_resource_dir: Path | None = None,
    extra_env: dict[str, str | Path] | None = None,
    gpus: str = "",
    log_dir: Path | None = None,
) -> int:
    command = build_docker_bash_command(
        ctx,
        image,
        body,
        nnunet_resource_dir=nnunet_resource_dir,
        extra_env=extra_env,
        gpus=gpus,
    )
    return run_step(ctx, name, "docker-bash", command, log_dir=log_dir)


def local_mask_all(ctx: PipelineContext) -> None:
    run_python_step(ctx, "04_check_t2tot1_outputs", "scripts/steps/4_check_t2tot1_outputs_v2.py", "--batch-dir", ctx.batch_dir)
    run_python_step(ctx, "05_check_nnunet_outputs", "scripts/steps/5_check_nnunet_outputs_v2.py", "--batch-dir", ctx.batch_dir)
    run_python_step(ctx, "06_mask_all", "scripts/steps/6_mask_all_v2.py", "--batch-dir", ctx.batch_dir)


def ensure_acpc_split(ctx: PipelineContext) -> None:
    if not (ctx.batch_dir / "3_skullstrip" / "data").is_dir():
        raise SystemExit("Cannot start ACPC: missing 3_skullstrip/data. Run stage 1 first.")
    run_python_step(ctx, "10_split_for_acpc", "scripts/steps/7_split_for_acpc_v2.py", "--batch-dir", ctx.batch_dir)


def run_denoise_selection(ctx: PipelineContext, args: argparse.Namespace) -> None:
    cmd_args = ["--batch-dir", ctx.batch_dir, "--pipeline-dir", ctx.pipeline_dir]
    if args.qc_excel:
        cmd_args.extend(["--qc-excel", Path(args.qc_excel).resolve()])
    cmd_args.extend(["--qc-mode", args.qc_mode])
    run_python_step(
        ctx,
        "20_select_denoise_candidates",
        "scripts/steps/10_select_denoise_candidates_v2.py",
        *cmd_args,
        allow_failure=True,
    )


def run_denoise_if_needed(ctx: PipelineContext, args: argparse.Namespace, *, mode: str = "selected") -> str:
    if not args.submit_denoise:
        return "skipped_by_flag"
    if mode == "existing-input":
        count = count_existing_denoise_inputs(ctx.batch_dir)
    else:
        count = count_csv_status(ctx.manifest_dir / "20_questionable_summary.csv", "selected_for_denoise")
    if count <= 0:
        return "skipped_no_input"

    moardiff_dir = normalize_external_path(args.moardiff_dir)
    checkpoint = normalize_external_path(args.moardiff_checkpoint)
    if args.denoise_backend == "windows":
        code = run_step(
            ctx,
            "21_denoise_moardiff",
            "windows-python",
            ctx.python_step(
                "scripts/steps/21_run_moardiff_denoise_v2.py",
                "--batch-dir",
                ctx.batch_dir,
                "--pipeline-dir",
                ctx.pipeline_dir,
                "--moardiff-dir",
                moardiff_dir,
                "--checkpoint",
                checkpoint,
                "--config-name",
                args.moardiff_config_name,
                "--run-id",
                "windows",
            ),
            log_dir=ctx.batch_dir / "5_questionable" / "logs",
        )
    elif args.denoise_backend == "wsl":
        code = run_wsl_job(
            ctx,
            "21_denoise_moardiff",
            'bash "$PIPELINE_DIR/scripts/jobs/denoise_moardiff.sh" "$BATCH_DIR" "$PIPELINE_DIR"',
            extra_env={
                "MOARDIFF_DIR": moardiff_dir,
                "MOARDIFF_CKPT": checkpoint,
                "MOARDIFF_CONFIG_NAME": args.moardiff_config_name,
            },
            log_dir=ctx.batch_dir / "5_questionable" / "logs",
        )
    elif args.denoise_backend == "docker":
        code = run_docker_job(
            ctx,
            "21_denoise_moardiff",
            args.docker_ai_image,
            'bash "$PIPELINE_DIR/scripts/jobs/denoise_moardiff.sh" "$BATCH_DIR" "$PIPELINE_DIR"',
            extra_env={
                "MOARDIFF_DIR": moardiff_dir,
                "MOARDIFF_CKPT": checkpoint,
                "MOARDIFF_CONFIG_NAME": args.moardiff_config_name,
            },
            gpus=args.docker_gpus,
            log_dir=ctx.batch_dir / "5_questionable" / "logs",
        )
    else:
        record_status(ctx, {"step": "21_denoise_moardiff", "backend": "skip", "status": "skipped"})
        return "skipped_backend"
    return args.denoise_backend if code == 0 else f"failed_rc_{code}"


def run_acpc_and_qc(ctx: PipelineContext, args: argparse.Namespace, jobs: dict[str, str]) -> None:
    if args.acpc_backend == "skip":
        record_status(ctx, {"step": "11_acpc", "backend": "skip", "status": "skipped"})
        return
    template_dir = normalize_external_path(args.template_dir)
    for branch in ["T1T2", "justT1"]:
        if branch_subject_count(ctx.batch_dir, branch) == 0:
            continue
        key = "t1t2" if branch == "T1T2" else "justt1"
        if args.acpc_backend == "wsl":
            acpc_code = run_wsl_job(
                ctx,
                f"11_acpc_{branch}",
                f'bash "$PIPELINE_DIR/scripts/jobs/acpc_preprocessing.sh" "$BATCH_DIR" "$PIPELINE_DIR" "{branch}"',
                extra_env={
                    "SMRI_TEMPLATE_DIR": template_dir,
                    "SMRI_ACPC_JOBS": str(args.acpc_jobs),
                },
                log_dir=ctx.batch_dir / "4_results" / "logs",
            )
            jobs[f"{key}_acpc_job_id"] = f"wsl:{branch}:rc{acpc_code}"
            qc_code = run_wsl_job(
                ctx,
                f"12_qc_acpc_{branch}",
                f'bash "$PIPELINE_DIR/scripts/jobs/qc_acpc_v2.sh" "$BATCH_DIR" "$PIPELINE_DIR" "{branch}"',
                log_dir=ctx.batch_dir / "4_results" / "logs",
            )
            jobs[f"{key}_qc_job_id"] = f"wsl:{branch}:rc{qc_code}"
        elif args.acpc_backend == "docker":
            acpc_code = run_docker_job(
                ctx,
                f"11_acpc_{branch}",
                args.docker_tools_image,
                f'bash "$PIPELINE_DIR/scripts/jobs/acpc_preprocessing.sh" "$BATCH_DIR" "$PIPELINE_DIR" "{branch}"',
                extra_env={
                    "SMRI_TEMPLATE_DIR": template_dir,
                    "SMRI_ACPC_JOBS": str(args.acpc_jobs),
                },
                log_dir=ctx.batch_dir / "4_results" / "logs",
            )
            jobs[f"{key}_acpc_job_id"] = f"docker:{branch}:rc{acpc_code}"
            qc_code = run_docker_job(
                ctx,
                f"12_qc_acpc_{branch}",
                args.docker_tools_image,
                f'bash "$PIPELINE_DIR/scripts/jobs/qc_acpc_v2.sh" "$BATCH_DIR" "$PIPELINE_DIR" "{branch}"',
                log_dir=ctx.batch_dir / "4_results" / "logs",
            )
            jobs[f"{key}_qc_job_id"] = f"docker:{branch}:rc{qc_code}"
        else:
            raise SystemExit("ACPC uses FSL/ANTs/Workbench and currently supports --acpc-backend wsl, docker, or skip.")
    run_python_step(ctx, "11_check_acpc_outputs", "scripts/steps/8_check_acpc_outputs_v2.py", "--batch-dir", ctx.batch_dir, allow_failure=True)
    run_python_step(ctx, "12_check_acpc_qc_outputs", "scripts/steps/9_check_acpc_qc_outputs_v2.py", "--batch-dir", ctx.batch_dir, allow_failure=True)


def run_stage1_heavy(ctx: PipelineContext, args: argparse.Namespace, jobs: dict[str, str]) -> None:
    nnunet_resource_dir = Path(args.nnunet_resource_dir).resolve()
    if args.registration_backend == "wsl":
        code = run_wsl_job(
            ctx,
            "03_registration_fsl",
            'bash "$PIPELINE_DIR/scripts/jobs/sMRI_pipeline_step0_reg2_v2.sh" "$BATCH_DIR" "$PIPELINE_DIR"',
            log_dir=ctx.batch_dir / "1_T2toT1" / "logs",
        )
        jobs["reg_job_id"] = f"wsl:registration:rc{code}"
    elif args.registration_backend == "docker":
        code = run_docker_job(
            ctx,
            "03_registration_fsl",
            args.docker_tools_image,
            'bash "$PIPELINE_DIR/scripts/jobs/sMRI_pipeline_step0_reg2_v2.sh" "$BATCH_DIR" "$PIPELINE_DIR"',
            log_dir=ctx.batch_dir / "1_T2toT1" / "logs",
        )
        jobs["reg_job_id"] = f"docker:registration:rc{code}"
    elif args.registration_backend == "skip":
        jobs["reg_job_id"] = "skipped"
    else:
        raise SystemExit("Registration uses FSL and currently supports --registration-backend wsl, docker, or skip.")

    if args.nnunet_backend == "wsl":
        code = run_wsl_job(
            ctx,
            "05_nnunet_task523",
            'bash "$PIPELINE_DIR/scripts/jobs/nnunet_task523.sh" "$BATCH_DIR" "$PIPELINE_DIR"',
            nnunet_resource_dir=nnunet_resource_dir,
            log_dir=ctx.batch_dir / "2_nnunet_output" / "logs",
        )
        jobs["nnunet_job_id"] = f"wsl:nnunet:rc{code}"
    elif args.nnunet_backend == "docker":
        code = run_docker_job(
            ctx,
            "05_nnunet_task523",
            args.docker_ai_image,
            'bash "$PIPELINE_DIR/scripts/jobs/nnunet_task523.sh" "$BATCH_DIR" "$PIPELINE_DIR"',
            nnunet_resource_dir=nnunet_resource_dir,
            gpus=args.docker_gpus,
            log_dir=ctx.batch_dir / "2_nnunet_output" / "logs",
        )
        jobs["nnunet_job_id"] = f"docker:nnunet:rc{code}"
    elif args.nnunet_backend == "windows":
        env = os.environ.copy()
        resource_data = nnunet_resource_dir / "nnUNetData"
        env.update(
            {
                "NNUNET_RESOURCE_DIR": str(nnunet_resource_dir),
                "nnUNet_raw_data_base": str(resource_data / "nnUNet_raw_data_base"),
                "nnUNet_preprocessed": str(resource_data / "nnUNet_preprocessed"),
                "RESULTS_FOLDER": str(resource_data / "RESULTS_FOLDER"),
                "PYTHONPATH": str(nnunet_resource_dir) + os.pathsep + env.get("PYTHONPATH", ""),
            }
        )
        command = [
            args.python_bin,
            "-m",
            "nnunet.inference.predict_simple",
            "-i",
            str(ctx.batch_dir / "2_nnunet_input" / "imagesTs"),
            "-o",
            str(ctx.batch_dir / "2_nnunet_output"),
            "-m",
            "3d_fullres",
            "-t",
            args.nnunet_task_name,
        ]
        code = run_step(ctx, "05_nnunet_task523", "windows-python", command, log_dir=ctx.batch_dir / "2_nnunet_output" / "logs", env=env)
        jobs["nnunet_job_id"] = f"windows:nnunet:rc{code}"
    else:
        jobs["nnunet_job_id"] = "skipped"

    if args.mask_backend == "windows":
        local_mask_all(ctx)
        jobs["mask_all_job_id"] = "windows"
    elif args.mask_backend == "wsl":
        code = run_wsl_job(
            ctx,
            "06_mask_all",
            'bash "$PIPELINE_DIR/scripts/jobs/mask_all.sh" "$BATCH_DIR" "$PIPELINE_DIR"',
            log_dir=ctx.batch_dir / "3_skullstrip" / "logs",
        )
        jobs["mask_all_job_id"] = f"wsl:mask:rc{code}"
    elif args.mask_backend == "docker":
        code = run_docker_job(
            ctx,
            "06_mask_all",
            args.docker_tools_image,
            'bash "$PIPELINE_DIR/scripts/jobs/mask_all.sh" "$BATCH_DIR" "$PIPELINE_DIR"',
            log_dir=ctx.batch_dir / "3_skullstrip" / "logs",
        )
        jobs["mask_all_job_id"] = f"docker:mask:rc{code}"
    else:
        jobs["mask_all_job_id"] = "skipped"


def write_report(ctx: PipelineContext) -> None:
    run_python_step(ctx, "99_write_preprocessing_report", "scripts/steps/11_write_preprocessing_report_v2.py", "--batch-dir", ctx.batch_dir)


def run_post_maskall_flow(ctx: PipelineContext, args: argparse.Namespace, jobs: dict[str, str]) -> None:
    if args.stage1_only:
        write_submitted_jobs(ctx, jobs)
        write_report(ctx)
        return
    ensure_acpc_split(ctx)
    run_acpc_and_qc(ctx, args, jobs)
    run_denoise_selection(ctx, args)
    jobs["denoise_job_id"] = run_denoise_if_needed(ctx, args, mode="selected")
    write_submitted_jobs(ctx, jobs)
    write_report(ctx)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    parser.add_argument("--qc-excel")
    parser.add_argument("--age-source", choices=["auto", "excel", "folder"], default="auto")
    parser.add_argument("--qc-mode", choices=["visual", "all-pass"], default="visual")
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--stage1-only", action="store_true")
    parser.add_argument("--no-denoise-submit", dest="submit_denoise", action="store_false")
    parser.set_defaults(submit_denoise=True)
    parser.add_argument("--acpc-start", action="store_true")
    parser.add_argument("--denoising-start", action="store_true")
    parser.add_argument("--denoising", action="store_true")
    parser.add_argument("--run-maskall-local", action="store_true")
    parser.add_argument("--registration-backend", type=parse_backend, default=os.environ.get("SMRI_REGISTRATION_BACKEND", "wsl"))
    parser.add_argument("--nnunet-backend", type=parse_backend, default=os.environ.get("SMRI_NNUNET_BACKEND", "wsl"))
    parser.add_argument("--mask-backend", type=parse_backend, default=os.environ.get("SMRI_MASK_BACKEND", "windows"))
    parser.add_argument("--acpc-backend", type=parse_backend, default=os.environ.get("SMRI_ACPC_BACKEND", "wsl"))
    parser.add_argument("--denoise-backend", type=parse_backend, default=os.environ.get("SMRI_DENOISE_BACKEND", "wsl"))
    parser.add_argument("--nnunet-resource-dir")
    parser.add_argument("--nnunet-task-name", default=os.environ.get("SMRI_NNUNET_TASK_NAME", "523"))
    parser.add_argument("--moardiff-dir")
    parser.add_argument("--moardiff-checkpoint")
    parser.add_argument("--moardiff-config-name", default=os.environ.get("MOARDIFF_CONFIG_NAME", "inference.yml"))
    parser.add_argument("--template-dir")
    parser.add_argument("--acpc-jobs", default=os.environ.get("SMRI_ACPC_JOBS", "4"))
    parser.add_argument("--docker-tools-image", default=os.environ.get("SMRI_DOCKER_TOOLS_IMAGE", "smri_pipeline_win:tools"))
    parser.add_argument("--docker-ai-image", default=os.environ.get("SMRI_DOCKER_AI_IMAGE", "smri_pipeline_win:ai"))
    parser.add_argument("--docker-gpus", default=os.environ.get("SMRI_DOCKER_GPUS", "all"))
    args = parser.parse_args(argv)
    resume_count = int(args.acpc_start) + int(args.denoising_start) + int(args.denoising)
    if resume_count > 1:
        parser.error("Use only one resume option: --acpc-start, --denoising-start, or --denoising.")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pipeline_dir = Path(__file__).resolve().parents[2]
    batch_dir = Path(args.batch_dir).expanduser().resolve()
    args.nnunet_resource_dir = args.nnunet_resource_dir or str(default_nnunet_resource(pipeline_dir))
    args.moardiff_dir = args.moardiff_dir or str(default_moardiff_dir(pipeline_dir))
    args.moardiff_checkpoint = args.moardiff_checkpoint or str(Path(args.moardiff_dir) / "exp" / "logs" / "finetuneDPM_with_age" / "ckpt_100000.pth")
    args.template_dir = args.template_dir or str(default_template_dir(pipeline_dir))

    ctx = PipelineContext(
        pipeline_dir=pipeline_dir,
        batch_dir=batch_dir,
        python_bin=args.python_bin,
        wsl_distro=args.wsl_distro,
        dry_run=False,
    )
    ensure_batch_layout(ctx.batch_dir)
    jobs: dict[str, str] = {}
    if args.run_maskall_local:
        require_wsl_if_needed(ctx, args.mask_backend)
        local_mask_all(ctx)
        write_report(ctx)
        return 0
    if args.denoising_start:
        require_wsl_if_needed(ctx, args.denoise_backend)
        run_denoise_selection(ctx, args)
        jobs["denoise_job_id"] = run_denoise_if_needed(ctx, args, mode="selected")
        write_submitted_jobs(ctx, jobs)
        write_report(ctx)
        return 0
    if args.denoising:
        require_wsl_if_needed(ctx, args.denoise_backend)
        if count_existing_denoise_inputs(ctx.batch_dir) == 0:
            run_denoise_selection(ctx, args)
        jobs["denoise_job_id"] = run_denoise_if_needed(ctx, args, mode="existing-input")
        write_submitted_jobs(ctx, jobs)
        write_report(ctx)
        return 0
    if args.acpc_start:
        require_wsl_if_needed(ctx, args.acpc_backend, args.denoise_backend)
        ensure_acpc_split(ctx)
        run_acpc_and_qc(ctx, args, jobs)
        run_denoise_selection(ctx, args)
        jobs["denoise_job_id"] = run_denoise_if_needed(ctx, args, mode="selected")
        write_submitted_jobs(ctx, jobs)
        write_report(ctx)
        return 0

    run_python_step(ctx, "01_standardize_t1_t2", "scripts/steps/1_standardize_t1_t2_v2.py", "--batch-dir", ctx.batch_dir, *(["--dry-run"] if args.dry_run else []))
    age_args: list[object] = ["--batch-dir", ctx.batch_dir, "--pipeline-dir", ctx.pipeline_dir]
    if args.qc_excel:
        age_args.extend(["--qc-excel", Path(args.qc_excel).resolve()])
    age_args.extend(["--age-source", args.age_source])
    if args.dry_run:
        age_args.append("--dry-run")
    run_python_step(ctx, "00_add_age_suffix", "scripts/steps/2_add_age_suffix_v2.py", *age_args)
    if args.dry_run:
        return 0
    run_python_step(ctx, "04_prepare_nnunet_input", "scripts/steps/3_prepare_nnunet_input_v2.py", "--batch-dir", ctx.batch_dir)
    if not args.submit:
        write_report(ctx)
        return 0
    if args.stage1_only:
        require_wsl_if_needed(ctx, args.registration_backend, args.nnunet_backend, args.mask_backend)
    else:
        require_wsl_if_needed(
            ctx,
            args.registration_backend,
            args.nnunet_backend,
            args.mask_backend,
            args.acpc_backend,
            args.denoise_backend,
        )
    run_stage1_heavy(ctx, args, jobs)
    run_post_maskall_flow(ctx, args, jobs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



