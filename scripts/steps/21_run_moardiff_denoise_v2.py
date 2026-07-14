#!/usr/bin/env python3
"""Run moAR-Diff inference for flat Stage 3 denoise inputs and collect outputs."""

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import nibabel as nib
import numpy as np
import yaml


EXPECTED_SHAPE = (192, 240, 192)
SUMMARY_NAME = "21_denoise_summary.csv"
AGE_RE = re.compile(r"^(?P<subject_id>.+)_(?P<age_month>\d{1,3})mo$", re.IGNORECASE)


FIELDS = [
    "subject_name",
    "subject_id",
    "age_month",
    "input_path",
    "output_path",
    "noisy_path",
    "final_path",
    "status",
    "error",
    "runtime_seconds",
    "shape",
    "checkpoint",
    "model_dir",
]


def parse_subject(name):
    match = AGE_RE.match(name)
    if not match:
        return "", "", f"cannot parse age suffix from subject folder: {name}"
    return match.group("subject_id"), match.group("age_month"), ""


def write_summary(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def row_for(subject_name, input_dir, batch_dir, checkpoint, model_dir):
    subject_id, age_month, age_error = parse_subject(subject_name)
    input_path = input_dir / subject_name / "T1.nii.gz"
    output_path = batch_dir / "5_questionable" / "output" / subject_name / "T1_age.nii.gz"
    noisy_path = batch_dir / "5_questionable" / "output" / subject_name / "noisy_T1.nii.gz"
    final_path = batch_dir / "5_questionable" / "final" / subject_name / "T1_acpc.nii.gz"
    row = {
        "subject_name": subject_name,
        "subject_id": subject_id,
        "age_month": age_month,
        "input_path": str(input_path),
        "output_path": str(output_path),
        "noisy_path": str(noisy_path),
        "final_path": str(final_path),
        "status": "pending",
        "error": "",
        "runtime_seconds": "",
        "shape": "",
        "checkpoint": str(checkpoint),
        "model_dir": str(model_dir),
    }
    if age_error:
        row["status"] = "failed"
        row["error"] = age_error
        return row
    if final_is_complete(batch_dir, subject_name, final_path, output_path):
        row["status"] = "skipped_existing"
        return row
    if output_path.is_file() and output_path.stat().st_size > 0:
        row["status"] = "pending_collect"
        return row
    if not input_path.is_file():
        row["status"] = "failed"
        row["error"] = "missing T1.nii.gz"
        return row
    try:
        shape = nib.load(str(input_path)).shape
    except Exception as exc:
        row["status"] = "failed"
        row["error"] = f"cannot read nifti: {exc}"
        return row
    row["shape"] = "x".join(str(x) for x in shape)
    if tuple(shape) != EXPECTED_SHAPE:
        row["status"] = "failed"
        row["error"] = f"shape mismatch, expected {'x'.join(map(str, EXPECTED_SHAPE))}"
    return row


def discover_subject_names(input_dir, output_dir, raw_dir):
    names = set()
    if input_dir.is_dir():
        names.update(p.name for p in input_dir.iterdir() if p.is_dir())
    if output_dir.is_dir():
        names.update(p.parent.name for p in output_dir.glob("*/T1_age.nii.gz") if p.is_file())
    if raw_dir.is_dir():
        names.update(p.parent.name for p in raw_dir.glob("*/T1_acpc.nii.gz") if p.is_file())
    return sorted(names)


def same_shape(path_a, path_b):
    try:
        return tuple(nib.load(str(path_a)).shape[:3]) == tuple(nib.load(str(path_b)).shape[:3])
    except Exception:
        return False


def final_is_complete(batch_dir, subject_name, final_path, output_path):
    raw_dir = batch_dir / "5_questionable" / "raw" / subject_name
    if not output_path.is_file() or output_path.stat().st_size == 0:
        return False
    raw_t1 = raw_dir / "T1_acpc.nii.gz"
    if not raw_t1.is_file() or not final_path.is_file() or final_path.stat().st_size == 0:
        return False
    if not same_shape(raw_t1, final_path):
        return False
    for item in raw_dir.iterdir():
        if item.name == "T1_acpc.nii.gz":
            continue
        dst = final_path.parent / item.name
        if item.is_dir():
            if not dst.is_dir():
                return False
        elif not dst.is_file() or dst.stat().st_size == 0:
            return False
    return True


def check_runtime_python(python_bin, require_cuda=True):
    code = r"""
import torch, torchvision
import numpy, nibabel, skimage, yaml, imageio, tqdm, einops, requests
print("cuda_available =", torch.cuda.is_available())
print("torch =", torch.__version__)
raise SystemExit(0 if (torch.cuda.is_available() or not REQUIRE_CUDA) else 3)
""".replace("REQUIRE_CUDA", "True" if require_cuda else "False")
    return subprocess.run([python_bin, "-c", code], text=True, capture_output=True)


def make_run_input(rows, input_dir, log_dir, run_id):
    run_input = log_dir / f"moardiff_run_input_{run_id}"
    if run_input.exists():
        shutil.rmtree(run_input)
    run_input.mkdir(parents=True)
    pending = [row for row in rows if row["status"] == "pending"]
    for row in pending:
        src = Path(row["input_path"]).parent
        dst = run_input / row["subject_name"]
        try:
            os.symlink(src, dst, target_is_directory=True)
        except OSError:
            shutil.copytree(src, dst)
    return run_input, pending


def make_config(model_dir, base_config_name, run_input, run_id):
    base_config = model_dir / "configs" / base_config_name
    if not base_config.is_file():
        raise FileNotFoundError(f"missing moAR-Diff config: {base_config}")
    with base_config.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    config.setdefault("data", {})["data_path"] = str(run_input)
    config_name = f"smri_inference_{run_id}.yml"
    config_path = model_dir / "configs" / config_name
    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)
    return config_name, config_path


def run_model(python_bin, model_dir, config_name, doc_name, checkpoint, output_dir):
    env = os.environ.copy()
    env["MOARDIFF_CKPT"] = str(checkpoint)
    env["MOARDIFF_OUTPUT_DIR"] = str(output_dir)
    command = [
        python_bin,
        "main.py",
        "--config",
        config_name,
        "--exp",
        "exp",
        "--doc",
        doc_name,
        "--inference_all",
        "--fid",
        "--timesteps",
        "50",
        "--eta",
        "0",
        "--seed",
        "46",
        "--ni",
    ]
    return subprocess.run(command, cwd=model_dir, env=env, text=True)


def load_resize_metadata(batch_dir, subject_name, raw_t1):
    meta_path = batch_dir / "5_questionable" / "input" / subject_name / "resize_meta.json"
    if meta_path.is_file():
        return json.loads(meta_path.read_text(encoding="utf-8"))

    data = nib.load(str(raw_t1)).get_fdata(dtype=np.float32)
    max_value = float(np.nanmax(data))
    if not np.isfinite(max_value) or max_value <= 0:
        raise ValueError("raw T1_acpc has no positive finite voxels")
    target_shape = EXPECTED_SHAPE
    thresholds = [0.0, max_value * 1e-8, max_value * 1e-7, max_value * 1e-6, max_value * 1e-5, max_value * 1e-4]
    for threshold in thresholds:
        coords = np.argwhere(data > threshold)
        if coords.size == 0:
            continue
        starts = coords.min(axis=0)
        stops = coords.max(axis=0) + 1
        crop_shape = stops - starts
        if all(int(crop_shape[i]) <= target_shape[i] for i in range(3)):
            return {
                "raw_shape": [int(x) for x in data.shape[:3]],
                "target_shape": [int(x) for x in target_shape],
                "bbox_start": [int(x) for x in starts],
                "bbox_stop": [int(x) for x in stops],
                "target_offset": [int((target_shape[i] - crop_shape[i]) // 2) for i in range(3)],
                "resize_threshold": float(threshold),
            }
    raise ValueError("cannot reconstruct resize metadata from raw T1_acpc")


def restore_to_raw_grid(denoised_path, raw_t1_path, metadata, final_path):
    raw_img = nib.load(str(raw_t1_path))
    denoised = nib.load(str(denoised_path)).get_fdata(dtype=np.float32)
    target_shape = tuple(int(x) for x in metadata["target_shape"])
    if tuple(denoised.shape[:3]) != target_shape:
        raise ValueError(f"denoised shape mismatch: got {denoised.shape[:3]}, expected {target_shape}")
    raw_shape = tuple(int(x) for x in metadata["raw_shape"])
    starts = [int(x) for x in metadata["bbox_start"]]
    stops = [int(x) for x in metadata["bbox_stop"]]
    offsets = [int(x) for x in metadata["target_offset"]]
    crop_shape = [stops[i] - starts[i] for i in range(3)]
    restored = raw_img.get_fdata(dtype=np.float32).copy()
    restored[
        starts[0]:stops[0],
        starts[1]:stops[1],
        starts[2]:stops[2],
    ] = denoised[
        offsets[0]:offsets[0] + crop_shape[0],
        offsets[1]:offsets[1] + crop_shape[1],
        offsets[2]:offsets[2] + crop_shape[2],
    ]
    nib.Nifti1Image(restored, raw_img.affine, raw_img.header).to_filename(str(final_path))


def collect_outputs(rows, batch_dir, runtime_seconds, model_failed=False, collect_statuses=None):
    collect_statuses = collect_statuses or {"pending"}
    for row in rows:
        if row["status"] not in collect_statuses:
            continue
        row["runtime_seconds"] = f"{runtime_seconds:.1f}"
        if model_failed:
            row["status"] = "failed"
            row["error"] = "moAR-Diff command failed"
            continue
        output_path = Path(row["output_path"])
        final_path = Path(row["final_path"])
        if not output_path.is_file() or output_path.stat().st_size == 0:
            row["status"] = "failed"
            row["error"] = "missing T1_age.nii.gz after inference"
            continue
        raw_dir = batch_dir / "5_questionable" / "raw" / row["subject_name"]
        if not raw_dir.is_dir():
            row["status"] = "failed"
            row["error"] = "missing raw subject dir for final assembly"
            continue
        raw_t1 = raw_dir / "T1_acpc.nii.gz"
        if not raw_t1.is_file():
            row["status"] = "failed"
            row["error"] = "missing raw T1_acpc.nii.gz for final assembly"
            continue
        final_path.parent.mkdir(parents=True, exist_ok=True)
        for item in raw_dir.iterdir():
            dst = final_path.parent / item.name
            if item.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(item, dst)
            else:
                shutil.copy2(item, dst)
        try:
            metadata = load_resize_metadata(batch_dir, row["subject_name"], raw_t1)
            restore_to_raw_grid(output_path, raw_t1, metadata, final_path)
        except Exception as exc:
            row["status"] = "failed"
            row["error"] = f"failed to restore denoise output to raw ACPC grid: {exc}"
            continue
        row["status"] = "success"
    return rows


def process(args):
    batch_dir = Path(args.batch_dir).resolve()
    pipeline_dir = Path(args.pipeline_dir).resolve()
    input_dir = batch_dir / "5_questionable" / "input"
    output_dir = batch_dir / "5_questionable" / "output"
    raw_dir = batch_dir / "5_questionable" / "raw"
    final_dir = batch_dir / "5_questionable" / "final"
    log_dir = batch_dir / "5_questionable" / "logs"
    summary = batch_dir / "manifests" / SUMMARY_NAME
    model_dir = Path(args.moardiff_dir).resolve()
    checkpoint = Path(args.checkpoint).resolve()
    python_bin = args.python_bin or sys.executable
    run_id = args.run_id or os.environ.get("SLURM_JOB_ID") or f"local_{int(time.time())}"

    output_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    if not model_dir.is_dir() or not (model_dir / "main.py").is_file():
        rows = [{field: "" for field in FIELDS}]
        rows[0].update({"status": "failed", "error": "missing moAR-Diff model dir or main.py", "model_dir": str(model_dir), "checkpoint": str(checkpoint)})
        write_summary(summary, rows)
        return 2
    if not checkpoint.is_file():
        rows = [{field: "" for field in FIELDS}]
        rows[0].update({"status": "failed", "error": "missing moAR-Diff checkpoint", "model_dir": str(model_dir), "checkpoint": str(checkpoint)})
        write_summary(summary, rows)
        return 2

    subject_names = discover_subject_names(input_dir, output_dir, raw_dir)
    rows = [row_for(subject_name, input_dir, batch_dir, checkpoint, model_dir) for subject_name in subject_names]
    if not rows:
        rows = [{field: "" for field in FIELDS}]
        rows[0].update({"status": "skipped", "error": "no subject folders", "model_dir": str(model_dir), "checkpoint": str(checkpoint)})
        write_summary(summary, rows)
        return 0

    rows = collect_outputs(rows, batch_dir, runtime_seconds=0.0, model_failed=False, collect_statuses={"pending_collect"})

    run_input, pending = make_run_input(rows, input_dir, log_dir, run_id)
    if not pending:
        write_summary(summary, rows)
        return 0

    dependency_check = check_runtime_python(python_bin, require_cuda=not args.allow_cpu)
    print(dependency_check.stdout, end="")
    if dependency_check.returncode != 0:
        print(dependency_check.stderr, file=sys.stderr, end="")
        for row in pending:
            row["status"] = "failed"
            row["error"] = "python dependency check failed or CUDA unavailable"
        write_summary(summary, rows)
        return dependency_check.returncode

    config_name, config_path = make_config(model_dir, args.config_name, run_input, run_id)
    print(f"Using moAR-Diff config: {config_path}")
    started = time.time()
    result = run_model(
        python_bin=python_bin,
        model_dir=model_dir,
        config_name=config_name,
        doc_name=f"smri_denoise_{run_id}",
        checkpoint=checkpoint,
        output_dir=output_dir,
    )
    runtime = time.time() - started
    rows = collect_outputs(rows, batch_dir, runtime_seconds=runtime, model_failed=result.returncode != 0)
    write_summary(summary, rows)
    return result.returncode


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--pipeline-dir", required=True)
    parser.add_argument("--moardiff-dir", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--config-name", default="inference.yml")
    parser.add_argument("--python-bin")
    parser.add_argument("--run-id")
    parser.add_argument("--allow-cpu", action="store_true")
    args = parser.parse_args(argv)
    return process(args)


if __name__ == "__main__":
    raise SystemExit(main())
