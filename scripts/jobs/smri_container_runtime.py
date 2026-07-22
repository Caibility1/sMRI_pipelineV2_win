#!/usr/bin/env python3
"""Run the existing Windows dispatchers directly inside the all-in-one image."""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path
from types import ModuleType

PYTHON_BIN = os.environ.get("PYTHON", sys.executable)


def run_native_job(
    ctx,
    name: str,
    image: str,
    body: str,
    *,
    nnunet_resource_dir: Path | None = None,
    extra_env: dict[str, str | Path] | None = None,
    gpus: str = "",
    log_dir: Path | None = None,
) -> int:
    """Execute a former Docker job in this already-running container."""
    del image, gpus
    env = os.environ.copy()
    env.update(
        {
            "PIPELINE_DIR": str(ctx.pipeline_dir),
            "BATCH_DIR": str(ctx.batch_dir),
            "PYTHON": ctx.python_bin,
            "SMRI_CONTAINER_RUNTIME": "1",
        }
    )
    if nnunet_resource_dir is not None:
        data_dir = Path(nnunet_resource_dir) / "nnUNetData"
        env.update(
            {
                "NNUNET_RESOURCE_DIR": str(nnunet_resource_dir),
                "nnUNet_raw_data_base": str(data_dir / "nnUNet_raw_data_base"),
                "nnUNet_preprocessed": str(data_dir / "nnUNet_preprocessed"),
                "RESULTS_FOLDER": str(data_dir / "RESULTS_FOLDER"),
            }
        )
    if extra_env:
        env.update({key: str(value) for key, value in extra_env.items()})
    utils = importlib.import_module("smri_windows_utils")
    return utils.run_step(
        ctx,
        name,
        "container-native",
        ["bash", "-lc", body],
        log_dir=log_dir,
        env=env,
    )


def prepare_module(name: str) -> ModuleType:
    module = importlib.import_module(name)
    module.run_docker_job = run_native_job
    module.check_docker_available = lambda: True
    return module


def add_if_missing(args: list[str], option: str, value: str) -> None:
    if option not in args:
        args.extend([option, value])


def run_preprocess(args: list[str]) -> int:
    os.environ.update(
        {
            "SMRI_REGISTRATION_BACKEND": "docker",
            "SMRI_NNUNET_BACKEND": "docker",
            "SMRI_MASK_BACKEND": "docker",
            "SMRI_ACPC_BACKEND": "docker",
            "SMRI_DENOISE_BACKEND": "docker",
        }
    )
    add_if_missing(args, "--python-bin", PYTHON_BIN)
    add_if_missing(args, "--nnunet-resource-dir", os.environ["NNUNET_RESOURCE_DIR"])
    add_if_missing(args, "--moardiff-dir", os.environ["MOARDIFF_DIR"])
    add_if_missing(args, "--moardiff-checkpoint", os.environ["MOARDIFF_CKPT"])
    add_if_missing(args, "--template-dir", os.environ["SMRI_TEMPLATE_DIR"])
    return prepare_module("smri_preprocessing_win").main(args)


def run_postprocess(args: list[str]) -> int:
    os.environ.update({"SMRI_PRESURF_BACKEND": "docker", "SMRI_RECON_BACKEND": "docker"})
    add_if_missing(args, "--python-bin", PYTHON_BIN)
    add_if_missing(args, "--freesurfer-home", os.environ["FREESURFER_HOME"])
    if os.environ.get("FS_LICENSE"):
        add_if_missing(args, "--fs-license", os.environ["FS_LICENSE"])
    return prepare_module("smri_presurf_recon_win").main(args)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preprocess", "postprocess"])
    parser.add_argument("pipeline_args", nargs=argparse.REMAINDER)
    parsed = parser.parse_args(argv)
    if not parsed.pipeline_args:
        parser.error("a batch directory or --help is required")
    if parsed.command == "preprocess":
        return run_preprocess(parsed.pipeline_args)
    return run_postprocess(parsed.pipeline_args)


if __name__ == "__main__":
    raise SystemExit(main())
