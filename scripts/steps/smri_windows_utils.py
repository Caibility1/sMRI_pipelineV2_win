#!/usr/bin/env python3
"""Shared helpers for Windows/WSL2 sMRI entrypoints."""

from __future__ import annotations

import argparse
import csv
import os
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable, Mapping, Sequence


STATUS_FIELDS = ["step", "backend", "status", "started", "finished", "returncode", "log", "note"]

BUNDLED_DOCKER_ENV = {
    "SMRI_DOCKER_BUNDLED_RESOURCES": "1",
    "NNUNET_RESOURCE_DIR": "/opt/smri/models/nnUNet",
    "nnUNet_raw_data_base": "/opt/smri/models/nnUNet/nnUNetData/nnUNet_raw_data_base",
    "nnUNet_preprocessed": "/opt/smri/models/nnUNet/nnUNetData/nnUNet_preprocessed",
    "RESULTS_FOLDER": "/opt/smri/models/nnUNet/nnUNetData/RESULTS_FOLDER",
    "MOARDIFF_DIR": "/opt/smri/models/denoise_diffusion/CBCP_UnDPM_with_age_finetune",
    "MOARDIFF_CKPT": "/opt/smri/models/denoise_diffusion/CBCP_UnDPM_with_age_finetune/exp/logs/finetuneDPM_with_age/ckpt_100000.pth",
    "SMRI_TEMPLATE_DIR": "/opt/smri/templates/UNC-BCP-4D-Infant-Brain-Volumetric-Atlas-Ver2/BCP-atlas-for_release-Ver2.0.0",
    "SMRI_WORKBENCH_BIN": "/opt/smri/workbench/bin_linux64",
    "FSLDIR": "/opt/fsl",
    "FREESURFER_HOME": "/opt/freesurfer",
    "ANTSPATH": "/opt/smri/tools-env/bin",
}


class PipelineContext:
    def __init__(
        self,
        pipeline_dir: Path,
        batch_dir: Path,
        python_bin: str = sys.executable,
        wsl_distro: str = "",
        dry_run: bool = False,
    ) -> None:
        self.pipeline_dir = Path(pipeline_dir)
        self.batch_dir = Path(batch_dir)
        self.python_bin = python_bin
        self.wsl_distro = wsl_distro
        self.dry_run = dry_run

    @property
    def manifest_dir(self) -> Path:
        return self.batch_dir / "manifests"

    @property
    def logs_dir(self) -> Path:
        return self.batch_dir / "logs"

    def python_step(self, relative_script: str, *args: object) -> list[str]:
        return [
            self.python_bin,
            str(self.pipeline_dir / relative_script),
            *[str(arg) for arg in args],
        ]


def resolve_existing_dir(path: str | Path, label: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"{label} does not exist: {resolved}")
    return resolved


def ensure_batch_layout(batch_dir: Path) -> None:
    for path in [
        batch_dir / "1_T2toT1" / "data",
        batch_dir / "1_T2toT1" / "qc",
        batch_dir / "1_T2toT1" / "logs",
        batch_dir / "2_nnunet_input" / "imagesTs",
        batch_dir / "2_nnunet_output" / "logs",
        batch_dir / "3_skullstrip" / "data",
        batch_dir / "3_skullstrip" / "logs",
        batch_dir / "4_results" / "logs",
        batch_dir / "5_questionable" / "logs",
        batch_dir / "manifests",
        batch_dir / "logs",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def quote_bash(value: str | Path) -> str:
    return shlex.quote(str(value).replace("\\", "/"))


def to_wsl_path(path: str | Path | PureWindowsPath) -> str:
    text = str(path)
    pure = PureWindowsPath(text)
    if text.startswith("\\\\") or str(pure).startswith("\\\\"):
        raise ValueError(f"UNC paths cannot be converted to /mnt paths automatically: {text}")
    drive = pure.drive.rstrip(":")
    if not drive:
        normalized = text.replace("\\", "/")
        if normalized.startswith("/"):
            return normalized
        raise ValueError(f"Cannot convert path without a drive letter to WSL: {text}")
    parts = [part for part in pure.parts[1:] if part not in {"\\", "/"}]
    return "/mnt/" + drive.lower() + ("/" + "/".join(parts) if parts else "")


def nnunet_env_exports(resource_dir: Path) -> dict[str, str]:
    data_dir = resource_dir / "nnUNetData"
    return {
        "NNUNET_RESOURCE_DIR": str(resource_dir),
        "nnUNet_raw_data_base": str(data_dir / "nnUNet_raw_data_base"),
        "nnUNet_preprocessed": str(data_dir / "nnUNet_preprocessed"),
        "RESULTS_FOLDER": str(data_dir / "RESULTS_FOLDER"),
    }



def docker_uses_bundled_resources() -> bool:
    value = os.environ.get("SMRI_DOCKER_BUNDLED_RESOURCES", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def default_fs_license_path(pipeline_dir: Path) -> Path:
    return pipeline_dir / "resources" / "software" / "freesurfer" / "license.txt"


def _docker_extra_env_with_defaults(ctx: PipelineContext, extra_env: Mapping[str, str | Path] | None) -> dict[str, str | Path]:
    env = dict(extra_env or {})
    for key in ("FSLDIR", "FREESURFER_HOME", "ANTSPATH", "CUDA_VISIBLE_DEVICES"):
        if key not in env:
            value = os.environ.get(key, "")
            if value:
                env[key] = value
    if "FS_LICENSE" not in env:
        fs_license = os.environ.get("FS_LICENSE", "")
        if fs_license:
            env["FS_LICENSE"] = fs_license
        else:
            default_license = default_fs_license_path(ctx.pipeline_dir)
            if default_license.is_file():
                env["FS_LICENSE"] = default_license
    return env

def _export_line(name: str, value: str) -> str:
    return f"export {name}={quote_bash(value)}"


def build_wsl_bash_command(
    ctx: PipelineContext,
    body: str,
    *,
    extra_env: Mapping[str, str | Path] | None = None,
    nnunet_resource_dir: Path | None = None,
) -> list[str]:
    exports: dict[str, str] = {
        "PIPELINE_DIR": to_wsl_path(ctx.pipeline_dir),
        "BATCH_DIR": to_wsl_path(ctx.batch_dir),
    }
    if nnunet_resource_dir is not None:
        exports.update({key: to_wsl_path(value) for key, value in nnunet_env_exports(nnunet_resource_dir).items()})
    if extra_env:
        for key, value in extra_env.items():
            value_text = str(value)
            exports[key] = to_wsl_path(value_text) if looks_like_windows_path(value_text) else value_text
    wsl_env = to_wsl_path(ctx.pipeline_dir / "environment" / "wsl_env.sh")
    script = (
        "set -euo pipefail\n"
        + "\n".join(_export_line(key, value) for key, value in exports.items())
        + "\n"
        + f"if [ -f {quote_bash(wsl_env)} ]; then set +u; source {quote_bash(wsl_env)} || true; set -u; fi\n"
        + body
        + "\n"
    )
    script_dir = ctx.logs_dir / "wsl_commands"
    script_dir.mkdir(parents=True, exist_ok=True)
    script_path = script_dir / f"wsl_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{os.getpid()}.sh"
    script_path.write_text(script, encoding="utf-8", newline="\n")

    command = ["wsl.exe"]
    if ctx.wsl_distro:
        command.extend(["-d", ctx.wsl_distro])
    command.extend(["--", "/bin/bash", to_wsl_path(script_path)])
    return command


def _relative_container_path(root: Path, mount_point: str, path: Path) -> str | None:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    suffix = relative.as_posix()
    return mount_point if suffix == "." else f"{mount_point}/{suffix}"


def to_container_path(ctx: PipelineContext, value: str | Path) -> str:
    text = str(value)
    if text.startswith("/"):
        return text
    if not looks_like_windows_path(text):
        return text
    path = Path(text).expanduser().resolve()
    for root, mount_point in [(ctx.pipeline_dir, "/pipeline"), (ctx.batch_dir, "/batch")]:
        mapped = _relative_container_path(root, mount_point, path)
        if mapped is not None:
            return mapped
    return text.replace("\\", "/")


def build_docker_bash_command(
    ctx: PipelineContext,
    image: str,
    body: str,
    *,
    extra_env: Mapping[str, str | Path] | None = None,
    nnunet_resource_dir: Path | None = None,
    gpus: str = "",
) -> list[str]:
    if not image:
        raise ValueError("Docker image name is required for docker backend")
    exports: dict[str, str] = {
        "PIPELINE_DIR": "/pipeline",
        "BATCH_DIR": "/batch",
    }
    bundled_resources = docker_uses_bundled_resources()
    if bundled_resources:
        exports.update(BUNDLED_DOCKER_ENV)
    mounts = [
        f"{ctx.pipeline_dir.resolve()}:/pipeline",
        f"{ctx.batch_dir.resolve()}:/batch",
    ]
    extra_mounts = os.environ.get("SMRI_DOCKER_EXTRA_MOUNTS", "")
    if extra_mounts:
        mounts.extend(mount.strip() for mount in extra_mounts.split(";") if mount.strip())
    if nnunet_resource_dir is not None and not bundled_resources:
        exports.update(nnunet_env_exports(PurePosixPath("/pipeline") / "resources" / "models" / "nnUNet"))
    effective_extra_env = _docker_extra_env_with_defaults(ctx, extra_env)
    if effective_extra_env:
        for key, value in effective_extra_env.items():
            value_text = str(value)
            if bundled_resources and key in BUNDLED_DOCKER_ENV:
                exports[key] = BUNDLED_DOCKER_ENV[key]
            elif key == "FS_LICENSE" and looks_like_windows_host_path(value_text):
                license_path = Path(value_text).expanduser().resolve()
                mapped = None
                for root, mount_point in [(ctx.pipeline_dir, "/pipeline"), (ctx.batch_dir, "/batch")]:
                    mapped = _relative_container_path(root, mount_point, license_path)
                    if mapped is not None:
                        break
                if mapped is None:
                    mounts.append(f"{license_path}:/licenses/freesurfer/license.txt:ro")
                    exports[key] = "/licenses/freesurfer/license.txt"
                else:
                    exports[key] = mapped
            else:
                exports[key] = to_container_path(ctx, value_text)
    container_env = "/pipeline/docker/container_env.sh"
    script = (
        "set -euo pipefail\n"
        + "\n".join(_export_line(key, value) for key, value in exports.items())
        + "\n"
        + f"if [ -f {quote_bash(container_env)} ]; then set +u; source {quote_bash(container_env)} || true; set -u; fi\n"
        + body
        + "\n"
    )
    script_dir = ctx.logs_dir / "docker_commands"
    script_dir.mkdir(parents=True, exist_ok=True)
    script_path = script_dir / f"docker_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{os.getpid()}.sh"
    script_path.write_text(script, encoding="utf-8", newline="\n")
    container_script = _relative_container_path(ctx.batch_dir, "/batch", script_path)
    if container_script is None:
        raise ValueError(f"Docker command script must be under batch dir: {script_path}")

    command = ["docker", "run", "--rm"]
    if gpus and gpus.lower() not in {"none", "0", "false", "no"}:
        command.extend(["--gpus", gpus])
    for mount in mounts:
        command.extend(["-v", mount])
    for key, value in exports.items():
        command.extend(["-e", f"{key}={value}"])
    command.extend([image, "/bin/bash", container_script])
    return command
def looks_like_windows_path(value: str) -> bool:
    return len(value) >= 3 and value[1:3] in {":\\", ":/"} and value[0].isalpha()


def looks_like_windows_host_path(value: str) -> bool:
    return looks_like_windows_path(value) or value.startswith("\\")

def normalize_external_path(value: str | Path) -> str:
    text = str(value)
    if text.startswith("/"):
        return text
    return str(Path(text).expanduser().resolve())


def run_command(
    command: Sequence[str],
    *,
    log_path: Path,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    dry_run: bool = False,
) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n## {datetime.now().isoformat(timespec='seconds')}\n")
        log.write("COMMAND: " + " ".join(str(part) for part in command) + "\n")
        if dry_run:
            log.write("DRY_RUN: command not executed\n")
            return 0
        process = subprocess.run(
            [str(part) for part in command],
            cwd=str(cwd) if cwd else None,
            env=dict(os.environ, **env) if env else None,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        log.write(f"RETURN_CODE: {process.returncode}\n")
        return process.returncode


def record_status(ctx: PipelineContext, row: Mapping[str, object], filename: str = "windows_status.csv") -> None:
    ctx.manifest_dir.mkdir(parents=True, exist_ok=True)
    path = ctx.manifest_dir / filename
    exists = path.is_file()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=STATUS_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({field: str(row.get(field, "")) for field in STATUS_FIELDS})


def run_step(
    ctx: PipelineContext,
    name: str,
    backend: str,
    command: Sequence[str],
    *,
    log_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> int:
    started_dt = datetime.now()
    started = started_dt.isoformat(timespec="seconds")
    log_root = log_dir or ctx.logs_dir
    log_path = log_root / f"{name}.log"
    print(f">>> START {name} [{backend}]", flush=True)
    print(f"    log: {log_path}", flush=True)
    code = run_command(command, log_path=log_path, env=env, dry_run=ctx.dry_run)
    finished_dt = datetime.now()
    finished = finished_dt.isoformat(timespec="seconds")
    elapsed = str(finished_dt - started_dt).split(".", 1)[0]
    status = "COMPLETE" if code == 0 else "FAILED"
    print(f"<<< {status} {name} [{backend}] rc={code} elapsed={elapsed}", flush=True)
    if code != 0:
        print(f"    check log: {log_path}", flush=True)
    record_status(
        ctx,
        {
            "step": name,
            "backend": backend,
            "status": "success" if code == 0 else "failed",
            "started": started,
            "finished": finished,
            "returncode": code,
            "log": log_path,
        },
    )
    return code


def run_python_step(ctx: PipelineContext, name: str, relative_script: str, *args: object, allow_failure: bool = False) -> int:
    code = run_step(ctx, name, "windows-python", ctx.python_step(relative_script, *args))
    if code != 0 and not allow_failure:
        raise SystemExit(code)
    return code


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("batch_dir")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--wsl-distro", default=os.environ.get("SMRI_WSL_DISTRO", ""))
    parser.add_argument("--dry-run", action="store_true")


def parse_backend(value: str) -> str:
    choices = {"skip", "windows", "wsl", "docker"}
    if value not in choices:
        raise argparse.ArgumentTypeError(f"backend must be one of: {', '.join(sorted(choices))}")
    return value


def default_nnunet_resource(pipeline_dir: Path) -> Path:
    return pipeline_dir / "resources" / "models" / "nnUNet"


def default_moardiff_dir(pipeline_dir: Path) -> Path:
    return pipeline_dir / "resources" / "models" / "denoise_diffusion" / "CBCP_UnDPM_with_age_finetune"


def default_template_dir(pipeline_dir: Path) -> Path:
    return (
        pipeline_dir
        / "resources"
        / "templates"
        / "UNC-BCP-4D-Infant-Brain-Volumetric-Atlas-Ver2"
        / "BCP-atlas-for_release-Ver2.0.0"
    )


def check_wsl_available(ctx: PipelineContext) -> bool:
    command = ["wsl.exe"]
    if ctx.wsl_distro:
        command.extend(["-d", ctx.wsl_distro])
    command.extend(["bash", "-lc", "true"])
    try:
        return subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    except FileNotFoundError:
        return False



def check_docker_available() -> bool:
    try:
        return subprocess.run(["docker", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    except FileNotFoundError:
        return False







